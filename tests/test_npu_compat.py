import sys
import types

from runtime import npu_compat

npu_compat.install_openvino_genai_compat()


def _fake_genai(calls):
    class FakeTokenizer:
        pass

    class FakeLLMPipeline:
        def __init__(self, model_path, device, **kwargs):
            calls.append(("llm", model_path, device, kwargs))

        def get_tokenizer(self):
            return FakeTokenizer()

    class FakeVLMPipeline:
        def __init__(self, model_path, device, **kwargs):
            calls.append(("vlm", model_path, device, kwargs))

        def get_tokenizer(self):
            return FakeTokenizer()

    class FakeEmbeddingPipeline:
        def __init__(self, model_path, device, **kwargs):
            calls.append(("embedding", model_path, device, kwargs))

    return types.SimpleNamespace(
        LLMPipeline=FakeLLMPipeline,
        VLMPipeline=FakeVLMPipeline,
        TextEmbeddingPipeline=FakeEmbeddingPipeline,
    )


def test_text_npu_factory_uses_catalog_response_budget(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai(calls))
    monkeypatch.setattr(npu_compat.engine, "is_openvino_available", lambda: True)

    result = npu_compat.create_engine(
        model_id="tinyllama-1.1b-chat-fp16",
        model_path="models/openvino/tinyllama-1.1b-chat-fp16",
        device="NPU",
        max_prompt_len=1536,
    )

    assert result.device == "NPU"
    assert calls == [
        (
            "llm",
            "models/openvino/tinyllama-1.1b-chat-fp16",
            "NPU",
            {"MAX_PROMPT_LEN": 1536, "MIN_RESPONSE_LEN": 512},
        )
    ]


def test_indexed_npu_vlm_nests_only_npu_properties(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai(calls))
    monkeypatch.setattr(npu_compat.engine, "is_openvino_available", lambda: True)

    npu_compat.create_engine(
        model_id="vision-test",
        model_path="models/openvino/vision-test",
        device="NPU.0",
        max_prompt_len=1536,
        max_response_len=512,
        cache_dir=tmp_path,
        backend="openvino-vlm",
    )

    assert calls == [
        (
            "vlm",
            "models/openvino/vision-test",
            "NPU.0",
            {
                "config": {
                    "CACHE_DIR": str(tmp_path),
                    "DEVICE_PROPERTIES": {
                        "NPU": {"MAX_PROMPT_LEN": 1536, "MIN_RESPONSE_LEN": 512}
                    },
                }
            },
        )
    ]


def test_npu_embedding_excludes_llm_generation_properties(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai(calls))
    monkeypatch.setattr(npu_compat.engine, "is_openvino_available", lambda: True)

    npu_compat.create_engine(
        model_id="bge-small-en-v1.5",
        model_path="models/openvino/bge-small-en-v1.5",
        device="NPU",
        max_prompt_len=512,
        cache_dir=tmp_path,
        backend="openvino-embeddings",
    )

    assert calls == [
        (
            "embedding",
            "models/openvino/bge-small-en-v1.5",
            "NPU",
            {"CACHE_DIR": str(tmp_path)},
        )
    ]
