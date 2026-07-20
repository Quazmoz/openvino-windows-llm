import base64
import io
import sys
import types

import pytest
from PIL import Image
from pydantic import ValidationError

from app import chat_format, multimodal
from app.model_registry import ModelConfig, make_catalog_entry
from app.openai_api import (
    ChatCompletionRequest,
    ChatMessage,
    DownloadCustomRequest,
    ModelRegisterRequest,
    ResponseRequest,
)
from runtime.openvino_engine import (
    GenParams,
    MockVisionEngine,
    OpenVINOVisionEngine,
    _streamer_status,
    create_engine,
)


def image_data_url(fmt: str = "PNG", size: tuple[int, int] = (3, 2)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", size, (12, 34, 56)).save(buffer, format=fmt)
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[fmt]
    return f"data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


def multimodal_content(url: str | None = None) -> list[dict]:
    return [
        {"type": "text", "text": "Describe this image."},
        {"type": "image_url", "image_url": {"url": url or image_data_url()}},
    ]


def test_decode_data_url_verifies_type_and_dimensions():
    payload = multimodal.decode_data_url(image_data_url(size=(7, 5)))
    assert payload.mime_type == "image/png"
    assert (payload.width, payload.height) == (7, 5)
    assert payload.data.startswith(b"\x89PNG")


def test_remote_and_mismatched_image_inputs_are_rejected():
    with pytest.raises(ValueError, match="remote image URLs are not fetched"):
        multimodal.decode_data_url("https://example.com/image.png")

    jpeg = image_data_url("JPEG").replace("data:image/jpeg", "data:image/png", 1)
    with pytest.raises(ValueError, match="not the declared image/png"):
        multimodal.decode_data_url(jpeg)


def test_openai_request_preflight_preserves_raw_parts_until_prompt_build():
    request = ChatCompletionRequest(
        model="vision",
        messages=[ChatMessage(role="user", content=multimodal_content())],
    )
    assert request.messages[0].content[1]["type"] == "image_url"

    response_request = ResponseRequest(
        model="vision",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "What is shown?"},
                    {"type": "input_image", "image_url": image_data_url()},
                ],
            }
        ],
    )
    assert response_request.input[0]["content"][1]["type"] == "input_image"

    with pytest.raises(ValidationError, match="base64 data URL"):
        ChatCompletionRequest(
            model="vision",
            messages=[
                ChatMessage(
                    role="user",
                    content=multimodal_content("https://example.com/private.png"),
                )
            ],
        )


def test_request_wide_count_is_rejected_before_image_decode(monkeypatch):
    def unexpected_decode(_url):  # pragma: no cover - assertion path
        raise AssertionError("over-limit preflight should run before decoding")

    monkeypatch.setattr(multimodal, "decode_data_url", unexpected_decode)
    messages = [
        ChatMessage(role="user", content=multimodal_content())
        for _ in range(multimodal.MAX_IMAGES_PER_REQUEST + 1)
    ]
    with pytest.raises(ValidationError, match="at most 4 images"):
        ChatCompletionRequest(model="vision", messages=messages)


def test_images_are_only_accepted_in_user_messages():
    with pytest.raises(ValidationError, match="only supported in user messages"):
        ChatCompletionRequest(
            model="vision",
            messages=[ChatMessage(role="system", content=multimodal_content())],
        )


def test_typed_transport_becomes_openvino_tags_and_is_consumed_once():
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )
    assert isinstance(messages[0]["content"], multimodal.MultimodalContent)
    assert "data:image" not in repr(messages[0]["content"])

    prepared, context_key = multimodal.prepare_vision_messages(messages)
    assert context_key
    assert "<ov_genai_image_0>" in prepared[0]["content"]
    prompt = multimodal.append_prompt_context(chat_format.render_chatml(prepared), context_key)

    clean_prompt, payloads = multimodal.consume_prompt_context(prompt)
    assert "ovllm-image-context" not in clean_prompt
    assert len(payloads) == 1
    assert (payloads[0].width, payloads[0].height) == (3, 2)

    with pytest.raises(RuntimeError, match="expired"):
        multimodal.consume_prompt_context(prompt)


def test_image_is_decoded_once_across_prompt_budget_candidates(monkeypatch):
    original = multimodal.decode_data_url
    calls = 0

    def counting_decode(url):
        nonlocal calls
        calls += 1
        return original(url)

    monkeypatch.setattr(multimodal, "decode_data_url", counting_decode)
    engine = MockVisionEngine("mock-vision")
    messages = chat_format.normalize_messages(
        [
            ChatMessage(role="user", content="old " * 200),
            ChatMessage(role="assistant", content="reply " * 200),
            ChatMessage(role="user", content=multimodal_content()),
        ]
    )
    assert calls == 1

    prompt, _ = chat_format.build_prompt_within_budget(
        messages,
        engine.apply_chat_template,
        engine.count_tokens,
        max_prompt_len=700,
    )
    assert calls == 1
    multimodal.discard_prompt_context(prompt)


def test_text_preparation_never_contains_encoded_image_bytes():
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )
    prepared = multimodal.prepare_text_messages(messages)
    assert "data:image" not in prepared[0]["content"]
    assert "not vision-capable" in prepared[0]["content"]


def test_exact_combined_pixel_limit_is_enforced():
    first = multimodal.ImagePayload("image/png", b"a", 5000, 4000)
    second = multimodal.ImagePayload("image/png", b"b", 5000, 4001)
    content = multimodal.MultimodalContent((first, second))
    with pytest.raises(ValueError, match="40,000,000-pixel"):
        multimodal.validate_request_contents([content])


def test_mock_vision_engine_generates_streams_and_reserves_image_tokens():
    engine = MockVisionEngine("mock-vision")
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )

    prompt = engine.apply_chat_template(messages)
    assert engine.count_tokens(prompt) >= 512
    result = engine.generate(prompt, params=GenParams())
    assert "1 image(s)" in result.text
    assert "3×2" in result.text

    second_prompt = engine.apply_chat_template(messages)
    stream = engine.stream(second_prompt, params=GenParams())
    chunks = []
    while True:
        chunk = stream.next_chunk()
        if chunk is None:
            break
        chunks.append(chunk)
    assert "1 image(s)" in "".join(chunks)
    assert stream.error is None


def test_factory_and_catalog_expose_vision_capability():
    engine = create_engine(
        model_id="mock-vision",
        model_path="models/openvino/mock-vision",
        device="CPU",
        force_mock=True,
        backend="openvino-vlm",
    )
    assert engine.supports_vision is True
    assert engine.backend == "mock-vlm"

    config = ModelConfig(
        id="vision",
        name="Vision",
        description="Local VLM",
        backend="openvino-vlm",
        model_path="models/openvino/vision",
        source_model="org/model",
        weight_format="int4",
        recommended_device="GPU",
        max_context_len=4096,
        max_output_tokens=512,
    )
    entry = make_catalog_entry(
        config,
        loaded=False,
        queued=False,
        loading=False,
        downloaded=False,
    )
    assert entry["supports_vision"] is True
    assert entry["capabilities"] == ["chat", "vision"]
    assert entry["input_modalities"] == ["text", "image"]


def test_budgeting_keeps_only_returned_prompt_context():
    engine = MockVisionEngine("mock-vision")
    messages = chat_format.normalize_messages(
        [
            ChatMessage(role="user", content="old " * 200),
            ChatMessage(role="assistant", content="reply " * 200),
            ChatMessage(role="user", content=multimodal_content()),
        ]
    )
    prompt, tokens = chat_format.build_prompt_within_budget(
        messages,
        engine.apply_chat_template,
        engine.count_tokens,
        max_prompt_len=700,
    )
    assert tokens > 0
    clean_prompt, payloads = multimodal.consume_prompt_context(prompt)
    assert "Describe this image" in clean_prompt
    assert len(payloads) == 1


def test_vision_context_capacity_uses_retryable_exception(monkeypatch):
    payload = multimodal.decode_data_url(image_data_url())
    monkeypatch.setattr(multimodal, "_CONTEXT_LIMIT", 0)
    with pytest.raises(multimodal.VisionCapacityError, match="Too many active vision requests"):
        multimodal._store_context([payload])


def test_real_vlm_wrapper_uses_openvino_keyword_contract(monkeypatch):
    calls = []

    class FakeTokenizer:
        def apply_chat_template(self, messages, add_generation_prompt=True):
            return chat_format.render_chatml(messages, add_generation_prompt)

        def encode(self, text):
            return type(
                "Encoded", (), {"input_ids": type("Ids", (), {"shape": [1, len(text)]})()}
            )()

    class FakeGenerationConfig:
        pass

    class FakePipeline:
        def __init__(self, model_path, device, **kwargs):
            calls.append(("init", model_path, device, kwargs))

        def get_tokenizer(self):
            return FakeTokenizer()

        def generate(self, prompt, **kwargs):
            calls.append(("generate", prompt, kwargs))
            streamer = kwargs.get("streamer")
            if streamer is not None:
                streamer("streamed ")
                return type("Result", (), {"texts": ["streamed "]})()
            return type("Result", (), {"texts": ["vision result"]})()

    fake_genai = types.SimpleNamespace(
        VLMPipeline=FakePipeline,
        GenerationConfig=FakeGenerationConfig,
    )
    monkeypatch.setitem(sys.modules, "openvino_genai", fake_genai)
    monkeypatch.setattr(multimodal, "to_openvino_tensors", lambda payloads: ["tensor"])

    engine = OpenVINOVisionEngine(
        "vision",
        "models/vision",
        "CPU",
        plugin_config={"CACHE_DIR": "cache"},
    )
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )
    result = engine.generate(engine.apply_chat_template(messages), GenParams(max_new_tokens=7))
    assert result.text == "vision result"
    generate_call = next(call for call in calls if call[0] == "generate")
    assert generate_call[2]["images"] == ["tensor"]
    assert isinstance(generate_call[2]["generation_config"], FakeGenerationConfig)

    handle = engine.stream(engine.apply_chat_template(messages), GenParams(max_new_tokens=7))
    assert handle.next_chunk() == "streamed "
    assert handle.next_chunk() is None
    assert handle.error is None
    stream_call = [call for call in calls if call[0] == "generate"][-1]
    assert stream_call[2]["images"] == ["tensor"]
    assert callable(stream_call[2]["streamer"])


def test_vlm_npu_plugin_config_is_nested_for_device_properties(monkeypatch):
    captured = {}

    class FakePipeline:
        def __init__(self, _model_path, _device, **kwargs):
            captured.update(kwargs)

        def get_tokenizer(self):
            return object()

    fake_genai = types.SimpleNamespace(VLMPipeline=FakePipeline)
    monkeypatch.setitem(sys.modules, "openvino_genai", fake_genai)
    OpenVINOVisionEngine(
        "vision",
        "models/vision",
        "NPU",
        plugin_config={"MAX_PROMPT_LEN": 2048},
    )
    assert captured == {"config": {"DEVICE_PROPERTIES": {"NPU": {"MAX_PROMPT_LEN": 2048}}}}


def test_streamer_status_supports_current_and_legacy_openvino_contracts():
    class Status:
        RUNNING = object()
        STOP = object()

    current = type("Current", (), {"StreamingStatus": Status})
    legacy = object()
    assert _streamer_status(current, stop=False) is Status.RUNNING
    assert _streamer_status(current, stop=True) is Status.STOP
    assert _streamer_status(legacy, stop=False) is False
    assert _streamer_status(legacy, stop=True) is True


@pytest.mark.parametrize("request_type", [ModelRegisterRequest, DownloadCustomRequest])
def test_model_registration_token_budget_is_cross_field_validated(request_type):
    base = {
        "model_id": "vision-model",
        "name": "Vision Model",
        "source_model": "org/model",
        "backend": "openvino-vlm",
        "max_context_len": 1024,
        "max_output_tokens": 1024,
    }
    with pytest.raises(ValidationError, match="max_context_len - 1"):
        request_type(**base)

    embedding = {
        **base,
        "backend": "openvino-embeddings",
        "max_output_tokens": 1,
    }
    with pytest.raises(ValidationError, match="max_output_tokens=0"):
        request_type(**embedding)


def test_preflight_enforces_limits_for_already_normalized_content():
    payload = multimodal.decode_data_url(image_data_url())
    normalized = multimodal.MultimodalContent(
        tuple(payload for _ in range(multimodal.MAX_IMAGES_PER_REQUEST + 1))
    )
    with pytest.raises(ValueError, match="at most 4 images"):
        multimodal.preflight_request_contents([normalized])


def test_context_markers_use_process_private_namespace():
    prompt = multimodal.append_prompt_context("hello", "a" * 32)
    assert "ovllm-image-context" in prompt
    assert multimodal._CONTEXT_NAMESPACE in prompt
    user_supplied = "hello\n<ovllm-image-context:" + ("b" * 32) + ">"
    assert multimodal.strip_prompt_context(user_supplied) == user_supplied


def test_request_text_and_content_part_limits_are_preflighted():
    with pytest.raises(ValueError, match="2,000,000 characters"):
        multimodal.preflight_request_contents(["x" * (multimodal.MAX_REQUEST_TEXT_CHARS + 1)])

    parts = ["x"] * (multimodal.MAX_CONTENT_PARTS_PER_REQUEST + 1)
    with pytest.raises(ValueError, match="1,024 content parts"):
        multimodal.preflight_request_contents([parts])


def test_chat_message_count_is_bounded():
    messages = [{"role": "user", "content": "x"}] * 4097
    with pytest.raises(ValidationError, match="at most 4096 items"):
        ChatCompletionRequest(model="text", messages=messages)
