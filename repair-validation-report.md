# Recent feature repair validation

- Patch exit: 1
- Install exit: 0
- Format exit: 0
- Format check exit: 1
- Lint exit: 1
- Test exit: 1

## Patch report
```text
PASS server imports hashlib
PASS generation helper accepts response_format
PASS generation helper stores response_format
PASS API-key stats use distinguishable fingerprints
PASS draft validation errors become HTTP 400
PASS chat completions forward response_format
PASS non-stream Responses API records per-key metrics
PASS validate chat structured-output and LoRA inputs
PASS validate Responses API LoRA alpha
PASS validate model conversion options
PASS validate custom download quantization options
PASS validate custom download device
PASS centralize converted OpenVINO directory validation
FAIL add draft model validation: expected one exact match in app/model_manager.py, found 0
FAIL load task accepts validated draft path: expected one exact match in app/model_manager.py, found 0
SKIP remove unvalidated draft path resolution: already applied
PASS validate draft before queueing load
FAIL pass validated draft path to load task: expected one exact match in app/model_manager.py, found 0
PASS preserve custom model backend
PASS converter catalog lookup returns task
PASS converter infers embedding task
PASS converter validates quantization and uses catalog task
PASS converter forwards resolved task
PASS engine imports hashlib
PASS engine imports Any
PASS mock embeddings are reproducible across processes
FAIL requested speculative decoding fails loudly and stays on requested device: expected one exact match in runtime/openvino_engine.py, found 0
PASS construct JSON-schema output config canonically
PASS construct JSON-object output config canonically
FAIL requested LoRA failures are not silently ignored: expected one exact match in runtime/openvino_engine.py, found 0
PASS custom model UI preserves description
PASS existing speculative test uses a text-generation draft
PASS existing speculative assertion uses valid draft
PASS existing key stats test expects distinct labels
PASS add recent feature regression tests

Replacement errors:
FAIL add draft model validation: expected one exact match in app/model_manager.py, found 0
FAIL load task accepts validated draft path: expected one exact match in app/model_manager.py, found 0
FAIL pass validated draft path to load task: expected one exact match in app/model_manager.py, found 0
FAIL requested speculative decoding fails loudly and stays on requested device: expected one exact match in runtime/openvino_engine.py, found 0
FAIL requested LoRA failures are not silently ignored: expected one exact match in runtime/openvino_engine.py, found 0
```

## Lint output
```text
F841 Local variable `draft_model_path` is assigned to but never used
   --> app/model_manager.py:473:9
    |
471 |             return existing
472 |
473 |         draft_model_path = self._resolve_draft_model_path(model_id, draft_model)
    |         ^^^^^^^^^^^^^^^^
474 |         device = device_check.normalize_device(device or self.settings.device)
475 |         cfg = self.catalog[model_id]
    |
help: Remove assignment to unused variable `draft_model_path`

B904 Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling
   --> app/server.py:545:17
    |
543 |             except Exception as exc:
544 |                 logger.error("Failed to query Hugging Face API: %s", exc)
545 |                 raise HTTPException(status_code=502, detail=f"Hugging Face API unreachable: {exc}")
    |                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
546 |
547 |         results = []
    |

F841 Local variable `task` is assigned to but never used
   --> app/server.py:582:9
    |
580 |         # 2. Schedule download and conversion
581 |         device = _normalize_device_or_400(None)
582 |         task = manager.schedule_convert(
    |         ^^^^
583 |             req.model_id,
584 |             device,
    |
help: Remove assignment to unused variable `task`

I001 [*] Import block is un-sorted or un-formatted
  --> app/telemetry.py:88:9
   |
87 |     try:
88 |         from runtime.device_check import get_core, available_devices
   |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
89 |
90 |         core = get_core()
   |
help: Organize imports

I001 [*] Import block is un-sorted or un-formatted
   --> tests/test_server_mock.py:813:5
    |
811 |   def test_multiple_api_keys_and_tracking():
812 |       # Test setting multiple API keys via Settings and tracking metrics
813 | /     from fastapi.testclient import TestClient
814 | |     from app.config import Settings
815 | |     from app.server import create_app
816 | |     from app.config import BASE_DIR
    | |___________________________________^
817 |
818 |       settings = Settings(
    |
help: Organize imports

Found 5 errors.
[*] 2 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

## Test output
```text
    raise app_exc from app_exc.__cause__ or app_exc.__context__
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/base.py:144: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/routing.py:660: in __call__
    await self.middleware_stack(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:2683: in app
    await route.handle(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:1266: in handle
    await super().handle(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/routing.py:276: in handle
    await self.app(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:150: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:136: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:690: in app
    raw_response = await run_endpoint_function(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:344: in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/server.py:420: in load_model
    task = manager.schedule_load(req.model, device, draft_model=req.draft_model)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <app.model_manager.ModelManager object at 0x7f684a3b58b0>
model_id = 'tinyllama-1.1b-chat-fp16', device = None
draft_model = 'smollm2-135m-fp16'

    def schedule_load(
        self,
        model_id: str,
        device: str | None = None,
        *,
        draft_model: str | None = None,
    ) -> asyncio.Task | None:
        if model_id not in self.catalog:
            logger.warning("Refusing to load unknown model '%s'", model_id)
            return None
        if model_id in self.engines:
            cfg = self.catalog[model_id]
            self._set_progress(model_id, "ready", f"{cfg.name} is already loaded.", percent=100)
            self._clear_status(model_id)
            return None
    
        existing = self.load_tasks.get(model_id)
        if existing and not existing.done():
            return existing
    
>       draft_model_path = self._resolve_draft_model_path(model_id, draft_model)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'

app/model_manager.py:473: AttributeError
---------------------------- Captured stdout setup -----------------------------
2026-07-13 15:59:25 [INFO] [-] Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
------------------------------ Captured log setup ------------------------------
INFO     ov-llm.server:server.py:187 Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
----------------------------- Captured stdout call -----------------------------
2026-07-13 15:59:25 [ERROR] [req-870788d24dc6] HTTP POST /v1/models/load failed - Error: 'ModelManager' object has no attribute '_resolve_draft_model_path' - Latency: 0.91ms
------------------------------ Captured log call -------------------------------
ERROR    ov-llm.server:server.py:219 HTTP POST /v1/models/load failed - Error: 'ModelManager' object has no attribute '_resolve_draft_model_path' - Latency: 0.91ms
--------------------------- Captured stdout teardown ---------------------------
2026-07-13 15:59:26 [INFO] [-] Server stopped; models unloaded.
---------------------------- Captured log teardown -----------------------------
INFO     ov-llm.server:server.py:193 Server stopped; models unloaded.
_________________________ test_dynamic_lora_generation _________________________

client = <starlette.testclient.TestClient object at 0x7f6849d41fa0>

    def test_dynamic_lora_generation(client):
        # Dynamic LoRA parameters inside completions call
        from unittest.mock import patch
    
>       _load_and_wait(client)

tests/test_server_mock.py:782: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
tests/test_server_mock.py:40: in _load_and_wait
    resp = client.post("/v1/models/load", json={"model": model_id})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/testclient.py:555: in post
    return super().post(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/httpx/_client.py:1144: in post
    return self.request(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/testclient.py:454: in request
    return super().request(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/testclient.py:356: in handle_request
    raise exc
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/testclient.py:353: in handle_request
    portal.call(self.app, scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/anyio/from_thread.py:338: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/anyio/from_thread.py:263: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/applications.py:1163: in __call__
    await super().__call__(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/applications.py:90: in __call__
    await self.middleware_stack(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/cors.py:88: in __call__
    await self.app(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/base.py:193: in __call__
    response = await self.dispatch_func(request, call_next)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/server.py:216: in request_id_and_logging_middleware
    response = await call_next(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/base.py:168: in call_next
    raise app_exc from app_exc.__cause__ or app_exc.__context__
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/base.py:144: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/routing.py:660: in __call__
    await self.middleware_stack(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:2683: in app
    await route.handle(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:1266: in handle
    await super().handle(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/routing.py:276: in handle
    await self.app(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:150: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:136: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:690: in app
    raw_response = await run_endpoint_function(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/routing.py:344: in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/server.py:420: in load_model
    task = manager.schedule_load(req.model, device, draft_model=req.draft_model)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <app.model_manager.ModelManager object at 0x7f684a3b44d0>
model_id = 'tinyllama-1.1b-chat-fp16', device = None, draft_model = None

    def schedule_load(
        self,
        model_id: str,
        device: str | None = None,
        *,
        draft_model: str | None = None,
    ) -> asyncio.Task | None:
        if model_id not in self.catalog:
            logger.warning("Refusing to load unknown model '%s'", model_id)
            return None
        if model_id in self.engines:
            cfg = self.catalog[model_id]
            self._set_progress(model_id, "ready", f"{cfg.name} is already loaded.", percent=100)
            self._clear_status(model_id)
            return None
    
        existing = self.load_tasks.get(model_id)
        if existing and not existing.done():
            return existing
    
>       draft_model_path = self._resolve_draft_model_path(model_id, draft_model)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'

app/model_manager.py:473: AttributeError
---------------------------- Captured stdout setup -----------------------------
2026-07-13 15:59:26 [INFO] [-] Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
------------------------------ Captured log setup ------------------------------
INFO     ov-llm.server:server.py:187 Starting OpenVINO Windows LLM server — MOCK (no OpenVINO)
----------------------------- Captured stdout call -----------------------------
2026-07-13 15:59:26 [ERROR] [req-7122a74a19c8] HTTP POST /v1/models/load failed - Error: 'ModelManager' object has no attribute '_resolve_draft_model_path' - Latency: 1.01ms
------------------------------ Captured log call -------------------------------
ERROR    ov-llm.server:server.py:219 HTTP POST /v1/models/load failed - Error: 'ModelManager' object has no attribute '_resolve_draft_model_path' - Latency: 1.01ms
--------------------------- Captured stdout teardown ---------------------------
2026-07-13 15:59:26 [INFO] [-] Server stopped; models unloaded.
---------------------------- Captured log teardown -----------------------------
INFO     ov-llm.server:server.py:193 Server stopped; models unloaded.
=============================== warnings summary ===============================
../../../../../opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/testclient.py:1
  /opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_model_converter.py::test_resolve_from_catalog_reads_models_json - ValueError: too many values to unpack (expected 3)
FAILED tests/test_recent_feature_regressions.py::test_structured_output_is_forwarded_to_generation - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_recent_feature_regressions.py::test_embedding_model_cannot_be_used_as_speculative_draft - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_recent_feature_regressions.py::test_nonstream_responses_are_attributed_to_the_calling_key - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_load_model_uses_requested_device - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_load_model_accepts_composite_device_in_mock_mode - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_load_then_chat_completion - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_chat_completion_stop_sequence_truncates - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_chat_completion_streaming_honors_stop - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_chat_completion_streaming - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_responses_non_streaming - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_responses_streaming_emits_events - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_metrics_accumulate_after_requests - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_stream_cancellation_frees_the_model_lock - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_embeddings_endpoint_success - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_embedding_model_guards - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_chat_completions_with_structured_output_format - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_speculative_decoding_load - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
FAILED tests/test_server_mock.py::test_dynamic_lora_generation - AttributeError: 'ModelManager' object has no attribute '_resolve_draft_model_path'
19 failed, 129 passed, 1 warning in 7.38s
```
