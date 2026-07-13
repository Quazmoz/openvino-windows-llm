# Recent feature repair validation

- Patch exit: 1
- Ruff fix exit: 1
- Format exit: 0
- Format check exit: 0
- Lint exit: 1
- Test exit: 1

## Patch output
```text
Traceback (most recent call last):
  File "<stdin>", line 54, in <module>
RuntimeError: Could not locate ModelManager._build_engine
```

## Lint output
```text
F821 Undefined name `Any`
   --> runtime/openvino_engine.py:116:60
    |
114 |         pass
115 |
116 |     def _build_adapters_config(self, params: GenParams) -> Any | None:
    |                                                            ^^^
117 |         return None
    |

Found 1 error.
```

## Test output
```text
...................................................................F.... [ 48%]
..............FFF..........................................F............ [ 97%]
....                                                                     [100%]
=================================== FAILURES ===================================
_________________ test_resolve_from_catalog_reads_models_json __________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f1137948050>
tmp_path = PosixPath('/home/runner/work/openvino-windows-llm/openvino-windows-llm/.tmp/pytest/test_resolve_from_catalog_read0')

    def test_resolve_from_catalog_reads_models_json(monkeypatch, tmp_path):
        catalog = {
            "m1": {
                "name": "M1",
                "model_path": "models/openvino/m1",
                "source_model": "org/m1",
                "weight_format": "int8",
            }
        }
        catalog_file = tmp_path / "models.json"
        catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
        monkeypatch.setenv("OV_LLM_MODELS_FILE", str(catalog_file))
    
>       source, output_dir, weight_format = mc._resolve_from_catalog("m1")
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       ValueError: too many values to unpack (expected 3)

tests/test_model_converter.py:66: ValueError
___________ test_embedding_model_cannot_be_used_as_speculative_draft ___________

tmp_path = PosixPath('/home/runner/work/openvino-windows-llm/openvino-windows-llm/.tmp/pytest/test_embedding_model_cannot_be0')

    def test_embedding_model_cannot_be_used_as_speculative_draft(tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            response = client.post(
                "/v1/models/load",
                json={"model": MODEL_ID, "draft_model": "bge-small-en-v1.5"},
            )
>           assert response.status_code == 400
E           assert 200 == 400
E            +  where 200 = <Response [200 OK]>.status_code

tests/test_recent_feature_regressions.py:86: AssertionError
----------------------------- Captured stdout call -----------------------------
2026-07-13 16:12:19 [INFO] [-] Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
2026-07-13 16:12:19 [INFO] [-] Using MOCK engine for 'tinyllama-1.1b-chat-fp16' (forced)
2026-07-13 16:12:19 [INFO] [req-9b83999facf6] HTTP POST /v1/models/load - Status: 200 - Latency: 1.76ms
2026-07-13 16:12:19 [INFO] [req-9b83999facf6] Loaded 'tinyllama-1.1b-chat-fp16' on CPU
2026-07-13 16:12:19 [INFO] [-] HTTP Request: POST http://testserver/v1/models/load "HTTP/1.1 200 OK"
2026-07-13 16:12:19 [INFO] [-] Server stopped; models unloaded.
------------------------------ Captured log call -------------------------------
INFO     ov-llm.server:server.py:187 Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
INFO     ov-llm.engine:openvino_engine.py:535 Using MOCK engine for 'tinyllama-1.1b-chat-fp16' (forced)
INFO     ov-llm.server:server.py:229 HTTP POST /v1/models/load - Status: 200 - Latency: 1.76ms
INFO     ov-llm.manager:model_manager.py:439 Loaded 'tinyllama-1.1b-chat-fp16' on CPU
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/models/load "HTTP/1.1 200 OK"
INFO     ov-llm.server:server.py:193 Server stopped; models unloaded.
_____________ test_custom_embedding_registration_preserves_backend _____________

tmp_path = PosixPath('/home/runner/work/openvino-windows-llm/openvino-windows-llm/.tmp/pytest/test_custom_embedding_registra0')

    def test_custom_embedding_registration_preserves_backend(tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            manager = client.app.state.manager
    
            def fake_schedule_convert(model_id, device=None, **kwargs):
                manager._set_status(model_id, "queued_convert")
                return object()
    
            manager.schedule_convert = fake_schedule_convert
            response = client.post(
                "/v1/models/download-custom",
                json={
                    "model_id": "custom-embedding-regression",
                    "name": "Custom Embedding Regression",
                    "source_model": "BAAI/bge-small-en-v1.5",
                    "backend": "openvino-embeddings",
                    "weight_format": "fp16",
                    "recommended_device": "CPU",
                    "max_context_len": 512,
                    "max_output_tokens": 0,
                    "load_after": False,
                },
            )
            assert response.status_code == 200, response.text
            config = manager.catalog["custom-embedding-regression"]
>           assert config.backend == "openvino-embeddings"
E           AssertionError: assert 'openvino-genai' == 'openvino-embeddings'
E             
E             - openvino-embeddings
E             + openvino-genai

tests/test_recent_feature_regressions.py:116: AssertionError
----------------------------- Captured stdout call -----------------------------
2026-07-13 16:12:19 [INFO] [-] Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
2026-07-13 16:12:19 [INFO] [req-b4de16ec0ed7] HTTP POST /v1/models/download-custom - Status: 200 - Latency: 1.88ms
2026-07-13 16:12:19 [INFO] [-] HTTP Request: POST http://testserver/v1/models/download-custom "HTTP/1.1 200 OK"
2026-07-13 16:12:19 [INFO] [-] Server stopped; models unloaded.
------------------------------ Captured log call -------------------------------
INFO     ov-llm.server:server.py:187 Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
INFO     ov-llm.server:server.py:229 HTTP POST /v1/models/download-custom - Status: 200 - Latency: 1.88ms
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/models/download-custom "HTTP/1.1 200 OK"
INFO     ov-llm.server:server.py:193 Server stopped; models unloaded.
__________ test_nonstream_responses_are_attributed_to_the_calling_key __________

tmp_path = PosixPath('/home/runner/work/openvino-windows-llm/openvino-windows-llm/.tmp/pytest/test_nonstream_responses_are_a0')

    def test_nonstream_responses_are_attributed_to_the_calling_key(tmp_path: Path) -> None:
        beta_headers = {"Authorization": "Bearer beta-key"}
        alpha_headers = {"Authorization": "Bearer alpha-key"}
        with _client(tmp_path, api_key="alpha-key,beta-key") as client:
            _load(client, headers=beta_headers)
            response = client.post(
                "/v1/responses",
                headers=beta_headers,
                json={"model": MODEL_ID, "input": "hello", "stream": False},
            )
            assert response.status_code == 200, response.text
    
            stats_response = client.get("/v1/keys/stats", headers=alpha_headers)
            assert stats_response.status_code == 200
            stats = stats_response.json()
            fingerprint = hashlib.sha256(b"beta-key").hexdigest()[:8]
            beta_stats = next(item for item in stats if item["key_name"].endswith(fingerprint))
>           assert beta_stats["requests"] == 1
E           assert 0 == 1

tests/test_recent_feature_regressions.py:137: AssertionError
----------------------------- Captured stdout call -----------------------------
2026-07-13 16:12:19 [INFO] [-] Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
2026-07-13 16:12:19 [INFO] [-] Using MOCK engine for 'tinyllama-1.1b-chat-fp16' (forced)
2026-07-13 16:12:19 [INFO] [req-d7b908e628a9] HTTP POST /v1/models/load - Status: 200 - Latency: 1.76ms
2026-07-13 16:12:19 [INFO] [req-d7b908e628a9] Loaded 'tinyllama-1.1b-chat-fp16' on CPU
2026-07-13 16:12:19 [INFO] [-] HTTP Request: POST http://testserver/v1/models/load "HTTP/1.1 200 OK"
2026-07-13 16:12:19 [INFO] [req-f70ea60acea6] HTTP GET /v1/system/status - Status: 200 - Latency: 6.46ms
2026-07-13 16:12:19 [INFO] [-] HTTP Request: GET http://testserver/v1/system/status "HTTP/1.1 200 OK"
2026-07-13 16:12:19 [INFO] [req-ae4f53d7c659] HTTP POST /v1/responses - Status: 200 - Latency: 1.76ms
2026-07-13 16:12:19 [INFO] [-] HTTP Request: POST http://testserver/v1/responses "HTTP/1.1 200 OK"
2026-07-13 16:12:19 [INFO] [req-e25caedaa687] HTTP GET /v1/keys/stats - Status: 200 - Latency: 0.62ms
2026-07-13 16:12:19 [INFO] [-] HTTP Request: GET http://testserver/v1/keys/stats "HTTP/1.1 200 OK"
2026-07-13 16:12:19 [INFO] [-] Server stopped; models unloaded.
------------------------------ Captured log call -------------------------------
INFO     ov-llm.server:server.py:187 Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
INFO     ov-llm.engine:openvino_engine.py:535 Using MOCK engine for 'tinyllama-1.1b-chat-fp16' (forced)
INFO     ov-llm.server:server.py:229 HTTP POST /v1/models/load - Status: 200 - Latency: 1.76ms
INFO     ov-llm.manager:model_manager.py:439 Loaded 'tinyllama-1.1b-chat-fp16' on CPU
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/models/load "HTTP/1.1 200 OK"
INFO     ov-llm.server:server.py:229 HTTP GET /v1/system/status - Status: 200 - Latency: 6.46ms
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/v1/system/status "HTTP/1.1 200 OK"
INFO     ov-llm.server:server.py:229 HTTP POST /v1/responses - Status: 200 - Latency: 1.76ms
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/responses "HTTP/1.1 200 OK"
INFO     ov-llm.server:server.py:229 HTTP GET /v1/keys/stats - Status: 200 - Latency: 0.62ms
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/v1/keys/stats "HTTP/1.1 200 OK"
INFO     ov-llm.server:server.py:193 Server stopped; models unloaded.
________________________ test_speculative_decoding_load ________________________

client = <starlette.testclient.TestClient object at 0x7f1127f58d70>

    def test_speculative_decoding_load(client):
        # Speculative decoding draft model parameter passed to /v1/models/load
        from unittest.mock import patch
    
        manager = client.app.state.manager
    
        with patch.object(manager, "_build_engine") as mock_build:
            resp = client.post(
                "/v1/models/load",
                json={
                    "model": "tinyllama-1.1b-chat-fp16",
                    "draft_model": "smollm2-135m-fp16",
                },
            )
            assert resp.status_code == 200
            # Wait for loading to finish
            import time
    
            for _ in range(50):
                if "tinyllama-1.1b-chat-fp16" not in manager.load_tasks:
                    break
                time.sleep(0.02)
    
            # Verify draft model path was resolved and passed
            mock_build.assert_called_once()
            args = mock_build.call_args[0]
            # First positional argument is model_id, second is device, third is draft_model_path
            assert args[0] == "tinyllama-1.1b-chat-fp16"
>           assert "smollm2-135m-fp16" in args[2]  # draft path contains model name
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           AssertionError: assert 'smollm2-135m-fp16' in '/home/runner/work/openvino-windows-llm/openvino-windows-llm/models/openvino/smollm2-135m-instruct-fp16'

tests/test_server_mock.py:775: AssertionError
---------------------------- Captured stdout setup -----------------------------
2026-07-13 16:12:23 [INFO] [-] Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
------------------------------ Captured log setup ------------------------------
INFO     ov-llm.server:server.py:187 Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
----------------------------- Captured stdout call -----------------------------
2026-07-13 16:12:23 [INFO] [req-a3b303a2cb99] HTTP POST /v1/models/load - Status: 200 - Latency: 1.85ms
2026-07-13 16:12:23 [INFO] [req-a3b303a2cb99] Loaded 'tinyllama-1.1b-chat-fp16' on <MagicMock name='_build_engine().device' id='139711923757056'>
2026-07-13 16:12:23 [INFO] [-] HTTP Request: POST http://testserver/v1/models/load "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     ov-llm.server:server.py:229 HTTP POST /v1/models/load - Status: 200 - Latency: 1.85ms
INFO     ov-llm.manager:model_manager.py:439 Loaded 'tinyllama-1.1b-chat-fp16' on <MagicMock name='_build_engine().device' id='139711923757056'>
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/models/load "HTTP/1.1 200 OK"
--------------------------- Captured stdout teardown ---------------------------
2026-07-13 16:12:23 [INFO] [-] Server stopped; models unloaded.
---------------------------- Captured log teardown -----------------------------
INFO     ov-llm.server:server.py:193 Server stopped; models unloaded.
=============================== warnings summary ===============================
../../../../../opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/testclient.py:1
  /opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_model_converter.py::test_resolve_from_catalog_reads_models_json - ValueError: too many values to unpack (expected 3)
FAILED tests/test_recent_feature_regressions.py::test_embedding_model_cannot_be_used_as_speculative_draft - assert 200 == 400
 +  where 200 = <Response [200 OK]>.status_code
FAILED tests/test_recent_feature_regressions.py::test_custom_embedding_registration_preserves_backend - AssertionError: assert 'openvino-genai' == 'openvino-embeddings'
  
  - openvino-embeddings
  + openvino-genai
FAILED tests/test_recent_feature_regressions.py::test_nonstream_responses_are_attributed_to_the_calling_key - assert 0 == 1
FAILED tests/test_server_mock.py::test_speculative_decoding_load - AssertionError: assert 'smollm2-135m-fp16' in '/home/runner/work/openvino-windows-llm/openvino-windows-llm/models/openvino/smollm2-135m-instruct-fp16'
5 failed, 143 passed, 1 warning in 5.11s
```
