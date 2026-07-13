# Recent feature repair validation

- Ruff fix exit: 1
- Format exit: 2
- Format check exit: 2
- Lint exit: 1
- Test exit: 2

## Follow-up patch report
```text
PASS insert draft validator
PASS load task accepts validated draft path
FAIL remove unvalidated draft resolution
PASS pass validated draft path
PASS fail loudly when speculative decoding cannot initialize
PASS fail loudly when LoRA cannot initialize
PASS chain Hugging Face search exception
PASS remove unused conversion task variable
PASS sort telemetry local import

Errors:
remove unvalidated draft resolution: expected one match, found 0
```

## Lint output
```text
invalid-syntax: Expected an indented block after function definition
   --> app/model_manager.py:349:5
    |
347 |     self, model_id: str, draft_model: str | None
348 | ) -> str | None:
349 |     if not draft_model:
    |     ^^
350 |         return None
351 |     if draft_model == model_id:
    |

invalid-syntax: Unexpected indentation
   --> runtime/openvino_engine.py:245:1
    |
244 | logger.info("Loading '%s' on %s from %s", model_id, self.device, self.model_path)
245 |         if draft_obj is not None:
    | ^^^^^^^^
246 |             self._pipe = ov_genai.LLMPipeline(
247 |                 self.model_path, self.device, draft_model=draft_obj, **config
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:256:1
    |
254 |         logger.info("Model '%s' ready on %s", model_id, self.device)
255 |
256 |     def _check_closed(self) -> None:
    | ^^^^
257 |         if self._closed:
258 |             raise RuntimeError(f"Engine for '{self.model_id}' is closed")
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:260:5
    |
258 |             raise RuntimeError(f"Engine for '{self.model_id}' is closed")
259 |
260 |     def apply_chat_template(self, messages: list[dict], add_generation_prompt: bool = True) -> str:
    |     ^
261 |         self._check_closed()
262 |         try:
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:274:5
    |
272 |             return chat_format.render_chatml(messages, add_generation_prompt)
273 |
274 |     def count_tokens(self, text: str) -> int:
    |     ^
275 |         self._check_closed()
276 |         try:
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:285:5
    |
283 |             return max(1, len(text) // 4)
284 |
285 |     def _build_config(self, params: GenParams):
    |     ^
286 |         cfg = self._ov.GenerationConfig()
287 |         cfg.max_new_tokens = int(params.max_new_tokens)
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:324:1
    |
322 |         return cfg
323 |
324 |     def _build_adapters_config(self, params: GenParams):
    | ^^^^
325 |         if not params.lora_path:
326 |             return None
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:330:1
    |
328 |         AdapterConfig = getattr(self._ov, "AdapterConfig", None)
329 |         if Adapter is None or AdapterConfig is None:
330 |     raise RuntimeError(
    | ^^^^
331 |         "This OpenVINO GenAI version does not support dynamic LoRA adapters."
332 |     )
    |

invalid-syntax: Unexpected indentation
   --> runtime/openvino_engine.py:333:1
    |
331 |         "This OpenVINO GenAI version does not support dynamic LoRA adapters."
332 |     )
333 |     try:
    | ^^^^
334 |         adapters_config = AdapterConfig()
335 |         adapters_config.add(
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:354:1
    |
352 |         return GenResult(text=text, completion_tokens=self.count_tokens(text))
353 |
354 |     def stream(self, prompt: str, params: GenParams) -> StreamHandle:
    | ^^^^
355 |         self._check_closed()
356 |         handle = StreamHandle()
    |

invalid-syntax: unindent does not match any outer indentation level
   --> runtime/openvino_engine.py:379:1
    |
377 |         return handle
378 |
379 |     def close(self) -> None:
    | ^^^^
380 |         if self._closed:
381 |             return
    |

invalid-syntax: Expected dedent, found end of file
   --> runtime/openvino_engine.py:547:1
    |
545 |         model_id, model_path, device, plugin_config, draft_model_path=draft_model_path
546 |     )
    |      ^
    |

Found 12 errors.
```

## Test output
```text

==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_benchmark_api.py _________________
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/python.py:508: in importtestmodule
    mod = import_path(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/pathlib.py:596: in import_path
    importlib.import_module(module_name)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:188: in exec_module
    exec(co, module.__dict__)
tests/test_benchmark_api.py:6: in <module>
    from app.server import create_app
app/server.py:33: in <module>
    from app import __version__, chat_format, model_manager, tools
E     File "/home/runner/work/openvino-windows-llm/openvino-windows-llm/app/model_manager.py", line 349
E       if not draft_model:
E       ^^
E   IndentationError: expected an indented block after function definition on line 346
_______________ ERROR collecting tests/test_benchmark_devices.py _______________
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/python.py:508: in importtestmodule
    mod = import_path(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/pathlib.py:596: in import_path
    importlib.import_module(module_name)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:188: in exec_module
    exec(co, module.__dict__)
tests/test_benchmark_devices.py:19: in <module>
    from scripts import benchmark_devices as bench  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
scripts/benchmark_devices.py:27: in <module>
    from runtime.openvino_engine import build_plugin_config  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E     File "/home/runner/work/openvino-windows-llm/openvino-windows-llm/runtime/openvino_engine.py", line 245
E       if draft_obj is not None:
E   IndentationError: unexpected indent
______________ ERROR collecting tests/test_model_registration.py _______________
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/python.py:508: in importtestmodule
    mod = import_path(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/pathlib.py:596: in import_path
    importlib.import_module(module_name)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:188: in exec_module
    exec(co, module.__dict__)
tests/test_model_registration.py:7: in <module>
    from app.model_manager import ModelManager
E     File "/home/runner/work/openvino-windows-llm/openvino-windows-llm/app/model_manager.py", line 349
E       if not draft_model:
E       ^^
E   IndentationError: expected an indented block after function definition on line 346
__________ ERROR collecting tests/test_recent_feature_regressions.py ___________
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/python.py:508: in importtestmodule
    mod = import_path(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/pathlib.py:596: in import_path
    importlib.import_module(module_name)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:188: in exec_module
    exec(co, module.__dict__)
tests/test_recent_feature_regressions.py:10: in <module>
    from app.server import create_app
app/server.py:33: in <module>
    from app import __version__, chat_format, model_manager, tools
E     File "/home/runner/work/openvino-windows-llm/openvino-windows-llm/app/model_manager.py", line 349
E       if not draft_model:
E       ^^
E   IndentationError: expected an indented block after function definition on line 346
__________________ ERROR collecting tests/test_server_mock.py __________________
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/python.py:508: in importtestmodule
    mod = import_path(
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/pathlib.py:596: in import_path
    importlib.import_module(module_name)
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/_pytest/assertion/rewrite.py:188: in exec_module
    exec(co, module.__dict__)
tests/test_server_mock.py:15: in <module>
    from app.model_manager import ModelManager
E     File "/home/runner/work/openvino-windows-llm/openvino-windows-llm/app/model_manager.py", line 349
E       if not draft_model:
E       ^^
E   IndentationError: expected an indented block after function definition on line 346
=============================== warnings summary ===============================
../../../../../opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/testclient.py:1
  /opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_benchmark_api.py
ERROR tests/test_benchmark_devices.py
ERROR tests/test_model_registration.py
ERROR tests/test_recent_feature_regressions.py
ERROR tests/test_server_mock.py
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!!
1 warning, 5 errors in 1.15s
```
