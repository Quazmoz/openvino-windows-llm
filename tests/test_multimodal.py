import base64
import io

import pytest
from PIL import Image
from pydantic import ValidationError

from app import chat_format, multimodal
from app.model_registry import ModelConfig, make_catalog_entry
from app.openai_api import ChatCompletionRequest, ChatMessage, ResponseRequest
from runtime.openvino_engine import MockVisionEngine, create_engine


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


def test_openai_request_models_validate_image_parts():
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


def test_transport_markers_become_openvino_image_tags_and_are_consumed_once():
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )
    assert "<ovllm-image>" in messages[0]["content"]

    prepared, context_key = multimodal.prepare_vision_messages(messages)
    assert context_key
    assert "<ov_genai_image_0>" in prepared[0]["content"]
    prompt = multimodal.append_prompt_context(
        chat_format.render_chatml(prepared), context_key
    )

    clean_prompt, payloads = multimodal.consume_prompt_context(prompt)
    assert "ovllm-image-context" not in clean_prompt
    assert len(payloads) == 1
    assert (payloads[0].width, payloads[0].height) == (3, 2)

    with pytest.raises(RuntimeError, match="expired"):
        multimodal.consume_prompt_context(prompt)


def test_text_model_never_receives_encoded_image_bytes():
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )
    prepared = multimodal.prepare_text_messages(messages)
    assert "data:image" not in prepared[0]["content"]
    assert "not vision-capable" in prepared[0]["content"]


def test_mock_vision_engine_generates_and_streams_image_summary():
    engine = MockVisionEngine("mock-vision")
    messages = chat_format.normalize_messages(
        [ChatMessage(role="user", content=multimodal_content())]
    )

    prompt = engine.apply_chat_template(messages)
    result = engine.generate(prompt, params=type("Params", (), {})())
    assert "1 image(s)" in result.text
    assert "3×2" in result.text

    second_prompt = engine.apply_chat_template(messages)
    stream = engine.stream(second_prompt, params=type("Params", (), {})())
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
        max_prompt_len=100,
    )
    assert tokens > 0
    clean_prompt, payloads = multimodal.consume_prompt_context(prompt)
    assert "Describe this image" in clean_prompt
    assert len(payloads) == 1
