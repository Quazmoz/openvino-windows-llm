"""FastAPI entry point: OpenAI-compatible routes, lifecycle, and the CLI.

Run via the CLI:
    python -m app.server --model tinyllama-1.1b-chat --device CPU
Or via uvicorn directly (settings come from environment variables):
    uvicorn app.server:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import logging
import os
import re
import secrets
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from app import __version__, chat_format, model_manager, tools
from app.config import BASE_DIR, Settings
from app.openai_api import (
    BenchmarkRunRequest,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatExportRequest,
    ChatMessage,
    ModelConvertRequest,
    ModelDeleteRequest,
    ModelLoadRequest,
    ModelRegisterRequest,
    ModelUnloadRequest,
    ResponseObject,
    ResponseOutputMessage,
    ResponseRequest,
    UsageInfo,
)
from app.rate_limit import RateLimitMiddleware
from app.telemetry import cpu_stats, disk_stats, gpu_stats, memory_stats
from runtime import device_check
from runtime.benchmark_runner import (
    DEFAULT_BENCHMARK_PROMPT,
    BenchmarkStore,
    run_benchmark_suite,
)
from runtime.openvino_engine import BaseEngine, GenParams

request_id_var = contextvars.ContextVar("request_id", default="")

# Client-supplied X-Request-ID values must be short and log-safe (no newlines /
# control characters that could forge log lines); anything else is replaced.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or "-"
        return True


# Configure logging to console with Request ID support
root_logger = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)
handler.addFilter(RequestIDFilter())
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

logger = logging.getLogger("ov-llm.server")
START_TIME = time.time()


WEB_DIR = BASE_DIR / "web"


def _load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded environment from %s", env_path)


def _normalize_device_or_400(device: str | None) -> str | None:
    if device is None:
        return None
    try:
        return device_check.validate_device_expression(device)
    except device_check.DeviceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Generation helpers ----------------------------------------------------


def _params_for(
    request_max_tokens: int | None,
    temperature: float | None,
    top_p: float | None,
    prompt_tokens: int,
    max_context_len: int,
    *,
    stop: list[str] | None = None,
    seed: int | None = None,
) -> GenParams:
    available = max(max_context_len - prompt_tokens - 8, 16)
    requested = request_max_tokens or 512
    max_new = max(min(requested, available), 16)
    temp = 0.7 if temperature is None else float(temperature)
    return GenParams(
        max_new_tokens=max_new,
        temperature=temp,
        top_p=1.0 if top_p is None else float(top_p),
        do_sample=temp > 0,
        stop=stop or None,
        seed=seed,
    )


def _build_chat_prompt(engine: BaseEngine, messages, max_prompt_len: int, system_override: str):
    dict_messages = chat_format.normalize_messages(messages, system_override)
    return chat_format.build_prompt_within_budget(
        dict_messages, engine.apply_chat_template, engine.count_tokens, max_prompt_len
    )


def _resolve_or_400(manager: model_manager.ModelManager, model_id: str) -> BaseEngine:
    try:
        return manager.resolve_engine(model_id)
    except model_manager.UnknownModel as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except model_manager.ModelLoading as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except model_manager.ModelNotLoaded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except model_manager.NoModelsLoaded as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def create_app(settings: Settings) -> FastAPI:
    manager = model_manager.ModelManager(settings)
    benchmark_store = BenchmarkStore(settings.benchmark_results_file)
    settings.validate(manager.catalog)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mode = "MOCK (no OpenVINO)" if manager.force_mock else f"device={settings.device}"
        logger.info("Starting OpenVINO Windows LLM server — %s", mode)
        await manager.startup()
        try:
            yield
        finally:
            await manager.shutdown()
            logger.info("Server stopped; models unloaded.")

    app = FastAPI(title="OpenVINO Windows LLM", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.manager = manager
    app.state.benchmark_store = benchmark_store

    # Rate limiting middleware
    if settings.rate_limit > 0:
        app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit)

    # Request ID and structured request/response logging middleware
    @app.middleware("http")
    async def request_id_and_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "")
        if not _REQUEST_ID_RE.fullmatch(request_id):
            request_id = f"req-{uuid.uuid4().hex[:12]}"

        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                "HTTP %s %s failed - Error: %s - Latency: %.2fms",
                request.method,
                request.url.path,
                str(exc),
                duration,
            )
            raise
        else:
            duration = (time.perf_counter() - start_time) * 1000
            logger.info(
                "HTTP %s %s - Status: %d - Latency: %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                duration,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)

    # Configure CORS middleware. Credentialed CORS is invalid with a wildcard
    # origin (browsers reject the combination), and this API authenticates via
    # the Authorization header rather than cookies, so credentials are only
    # enabled when explicit origins are configured.
    origins = [orig.strip() for orig in settings.cors_origins.split(",") if orig.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- auth (optional) ---------------------------------------------------

    def require_api_key(authorization: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        expected = f"Bearer {settings.api_key}"
        # Constant-time comparison so a wrong key can't be recovered via timing.
        # Compare bytes to tolerate any non-ASCII header without raising.
        if authorization is None or not secrets.compare_digest(
            authorization.encode("utf-8"), expected.encode("utf-8")
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    auth = [Depends(require_api_key)]

    # --- UI + health -------------------------------------------------------

    @app.get("/", response_class=FileResponse)
    async def index():
        return FileResponse(
            WEB_DIR / "index.html",
            headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    @app.get("/health")
    async def health():
        loading_count = manager.loading_count()
        return {
            "status": "ok" if loading_count == 0 else "busy",
            "version": app.version,
            "uptime_seconds": int(time.time() - START_TIME),
            "mock": manager.force_mock,
            "device": settings.device,
            "openvino": device_check.is_openvino_available(),
            "models_loaded": len(manager.engines),
            "loading_count": loading_count,
            "any_busy": manager.any_busy(),
        }

    @app.get("/health/live")
    async def health_live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready(response: Response):
        loading_count = manager.loading_count()
        if loading_count > 0:
            response.status_code = 503
            return {"status": "busy", "message": "Models are loading"}
        return {"status": "ready"}

    # --- models ------------------------------------------------------------

    @app.get("/v1/models", dependencies=auth)
    async def list_models():
        data = []
        for model_id in manager.catalog:
            entry = manager.catalog_entry(model_id)
            data.append(
                {
                    "id": model_id,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "openvino",
                    "name": entry["name"],
                    "description": entry["description"],
                    "status": entry["status"],
                }
            )
        return {"object": "list", "data": data}

    @app.post("/v1/models/register", dependencies=auth)
    async def register_model(req: ModelRegisterRequest):
        try:
            cfg = manager.register_model(req)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "registered",
            "message": f"Successfully registered {cfg.name}.",
            "model": manager.catalog_entry(cfg.id),
        }

    @app.post("/v1/models/load", dependencies=auth)
    async def load_model(req: ModelLoadRequest):
        if req.model not in manager.catalog:
            raise HTTPException(status_code=404, detail=f"Unknown model '{req.model}'")
        device = _normalize_device_or_400(req.device)

        task = manager.schedule_load(req.model, device)
        entry = manager.catalog_entry(req.model)
        if task is None and entry["is_loaded"]:
            return {
                "status": "loaded",
                "message": f"{entry['name']} is already loaded.",
                "model": entry,
            }
        return {
            "status": entry["status"],
            "message": f"Loading {entry['name']}. First load can take a while.",
            "model": entry,
        }

    @app.post("/v1/models/convert", dependencies=auth)
    async def convert_model(req: ModelConvertRequest):
        if req.model not in manager.catalog:
            raise HTTPException(status_code=404, detail=f"Unknown model '{req.model}'")
        device = _normalize_device_or_400(req.device)
        cfg = manager.catalog[req.model]
        if not cfg.source_model:
            raise HTTPException(
                status_code=400, detail=f"Model '{req.model}' has no source model configured"
            )

        task = manager.schedule_convert(req.model, device, load_after=req.load_after)
        entry = manager.catalog_entry(req.model)
        if task is None and entry["is_downloaded"]:
            return {
                "status": entry["status"],
                "message": f"{entry['name']} is already converted.",
                "model": entry,
            }
        return {
            "status": entry["status"],
            "message": f"Converting {entry['name']}. This may take several minutes.",
            "model": entry,
        }

    @app.post("/v1/models/unload", dependencies=auth)
    async def unload_model(req: ModelUnloadRequest):
        if req.model not in manager.catalog:
            raise HTTPException(status_code=404, detail=f"Unknown model '{req.model}'")
        if req.model not in manager.engines:
            raise HTTPException(status_code=409, detail=f"Model '{req.model}' is not loaded")
        lock = manager.locks.get(req.model)
        if lock and lock.locked():
            raise HTTPException(status_code=409, detail=f"Model '{req.model}' is busy")

        manager.unload(req.model)
        entry = manager.catalog_entry(req.model)
        return {"status": "unloaded", "message": f"Unloaded {entry['name']}.", "model": entry}

    @app.post("/v1/models/delete", dependencies=auth)
    async def delete_model(req: ModelDeleteRequest):
        if req.model not in manager.catalog:
            raise HTTPException(status_code=404, detail=f"Unknown model '{req.model}'")
        if req.model in manager.engines:
            raise HTTPException(
                status_code=409,
                detail=f"Model '{req.model}' is loaded. Unload it before deleting.",
            )
        override = manager.status_overrides.get(req.model, {})
        if override.get("status") in {"queued", "loading"}:
            raise HTTPException(status_code=409, detail=f"Model '{req.model}' is still loading")

        try:
            # Deleting a multi-GB IR directory can take a while; keep it off the event loop.
            result = await asyncio.to_thread(manager.delete, req.model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc

        entry = manager.catalog_entry(req.model)
        freed_gb = round(result["freed_bytes"] / (1024**3), 2)
        if not result["deleted"]:
            return {
                "status": "noop",
                "message": f"No local files for {entry['name']}.",
                "freed_gb": 0.0,
                "model": entry,
            }
        return {
            "status": "deleted",
            "message": f"Deleted {entry['name']} ({freed_gb} GB freed).",
            "freed_gb": freed_gb,
            "freed_bytes": result["freed_bytes"],
            "model": entry,
        }

    # --- devices + system status ------------------------------------------

    @app.get("/v1/devices", dependencies=auth)
    async def devices():
        available = device_check.available_devices()
        return {
            "default_device": settings.device,
            "openvino_available": device_check.is_openvino_available(),
            "mock": manager.force_mock,
            "available": available,
            "devices": device_check.device_details(),
            "suggestions": device_check.suggested_device_targets(available),
            "supported_examples": device_check.supported_device_examples(),
        }

    @app.get("/v1/system/status", dependencies=auth)
    async def system_status():
        entries = manager.catalog_entries()
        available = device_check.available_devices()
        # GPU property queries and the models-dir size walk both touch
        # drivers/disk; run them off the event loop since the UI polls this.
        gpu, disk = await asyncio.gather(
            asyncio.to_thread(gpu_stats),
            asyncio.to_thread(disk_stats, settings.models_dir),
        )
        return {
            "memory": memory_stats(),
            "cpu": cpu_stats(),
            "gpu": gpu,
            "device": {
                "default": settings.device,
                "mock": manager.force_mock,
                "available": available,
                "suggestions": device_check.suggested_device_targets(available),
                "loaded": dict(manager.devices),
                "busy": manager.any_busy(),
            },
            "models": {
                "loaded": list(manager.engines.keys()),
                "count": len(manager.engines),
                "loading_count": manager.loading_count(),
                "available": entries,
            },
            "disk": {
                "models_dir": str(settings.models_dir.resolve()),
                **disk,
            },
            "metrics": manager.metrics_summary(),
            "events": manager.recent_events(),
        }

    # --- benchmarks --------------------------------------------------------

    def _benchmark_models_or_400(req: BenchmarkRunRequest) -> list[str]:
        requested = []
        if req.model:
            requested.append(req.model)
        if req.models:
            requested.extend(req.models)
        requested = [model_id for model_id in dict.fromkeys(requested) if model_id]
        if not requested:
            raise HTTPException(status_code=400, detail="Provide at least one benchmark model.")
        unknown = [model_id for model_id in requested if model_id not in manager.catalog]
        if unknown:
            raise HTTPException(status_code=404, detail=f"Unknown benchmark model '{unknown[0]}'")
        return requested

    def _benchmark_devices_or_400(req: BenchmarkRunRequest) -> list[str]:
        if not req.devices:
            raise HTTPException(status_code=400, detail="Provide at least one benchmark device.")
        devices = []
        for device in req.devices:
            devices.append(_normalize_device_or_400(device))
        return [device for device in dict.fromkeys(devices) if device]

    @app.post("/v1/benchmarks/run", dependencies=auth)
    async def run_benchmarks(req: BenchmarkRunRequest):
        model_ids = _benchmark_models_or_400(req)
        devices = _benchmark_devices_or_400(req)
        prompt = (req.prompt or DEFAULT_BENCHMARK_PROMPT).strip() or DEFAULT_BENCHMARK_PROMPT
        try:
            run = await run_benchmark_suite(
                manager,
                model_ids=model_ids,
                devices=devices,
                prompt=prompt,
                max_tokens=req.max_tokens,
                runs=req.runs,
            )
        except device_check.DeviceValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await asyncio.to_thread(benchmark_store.append, run)
        manager.emit_event(
            "info",
            f"Benchmarked {len(model_ids)} model(s) across {len(devices)} device target(s)",
        )
        return run

    @app.get("/v1/benchmarks", dependencies=auth)
    async def list_benchmarks():
        runs = await asyncio.to_thread(benchmark_store.list_runs)
        return {"object": "list", "data": list(reversed(runs))}

    @app.get("/v1/benchmarks/latest", dependencies=auth)
    async def latest_benchmark():
        run = await asyncio.to_thread(benchmark_store.latest)
        return {
            "run": run,
            "recommendation": run.get("recommendation") if run else None,
        }

    @app.delete("/v1/benchmarks", dependencies=auth)
    async def clear_benchmarks():
        deleted = await asyncio.to_thread(benchmark_store.clear)
        manager.emit_event("info", "Cleared benchmark results")
        return {"status": "cleared", "deleted_runs": deleted}

    # --- conversation export -----------------------------------------------

    @app.post("/v1/chat/export", dependencies=auth)
    async def export_chat(request: ChatExportRequest):
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages to export")

        now = datetime.now(UTC)
        ts_display = now.strftime("%Y-%m-%d %H:%M UTC")
        ts_file = now.strftime("%Y%m%d-%H%M%S")

        lines: list[str] = []
        lines.append("# Chat Export — OpenVINO LLM")
        lines.append("")
        meta_parts = [f"**Exported:** {ts_display}"]
        if request.model:
            meta_parts.append(f"**Model:** {request.model}")
        if request.device:
            meta_parts.append(f"**Device:** {request.device}")
        lines.append(" · ".join(meta_parts))
        lines.append("")
        lines.append("---")
        lines.append("")

        for msg in request.messages:
            role = (msg.role or "unknown").capitalize()
            content = (msg.content or "").strip()
            if msg.role == "user":
                lines.append(f"### 🧑 {role}")
                lines.append("")
                for line in content.splitlines():
                    lines.append(f"> {line}")
            elif msg.role == "system":
                lines.append(f"### ⚙️ {role}")
                lines.append("")
                lines.append(f"_{content}_")
            else:
                lines.append(f"### ✨ {role}")
                lines.append("")
                lines.append(content)
            lines.append("")

        body = "\n".join(lines)
        filename = f"chat-export-{ts_file}.md"
        return Response(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # --- chat completions --------------------------------------------------

    @app.post("/v1/chat/completions", dependencies=auth)
    async def chat_completions(request: ChatCompletionRequest):
        engine = _resolve_or_400(manager, request.model)
        cfg = manager.config_for(engine.model_id)
        max_context_len = cfg.max_context_len if cfg else 2048
        max_prompt_len = cfg.max_prompt_len if cfg else 1536

        use_tools = bool(request.tools) and request.tool_choice != "none"
        system_override = (
            tools.format_tools_for_prompt(request.tools, request.tool_choice) if use_tools else ""
        )

        prompt, prompt_tokens = _build_chat_prompt(
            engine, request.messages, max_prompt_len, system_override
        )
        params = _params_for(
            request.max_tokens,
            request.temperature,
            request.top_p,
            prompt_tokens,
            max_context_len,
            stop=chat_format.normalize_stop(request.stop),
            seed=request.seed,
        )

        if request.stream:
            req_id = request_id_var.get()
            return StreamingResponse(
                _stream_chat(engine, request, prompt, prompt_tokens, params, use_tools, req_id),
                media_type="text/event-stream",
            )
        return await _complete_chat(
            engine, request, prompt, prompt_tokens, params, use_tools, max_prompt_len
        )

    async def _complete_chat(
        engine, request, prompt, prompt_tokens, params, use_tools, max_prompt_len
    ):
        MAX_RETRIES = 2
        start = time.perf_counter()
        text = ""
        completion_tokens = 0
        current_prompt = prompt
        current_prompt_tokens = prompt_tokens

        for attempt in range(MAX_RETRIES + 1):
            result = await manager.generate(engine, current_prompt, params)
            text = result.text
            completion_tokens = result.completion_tokens
            if use_tools and tools.detect_incomplete_tool_call(text) and attempt < MAX_RETRIES:
                logger.warning("Malformed tool call; retry %d/%d", attempt + 1, MAX_RETRIES)
                retry_messages = list(request.messages) + [
                    ChatMessage(role="assistant", content=text),
                    ChatMessage(role="user", content=tools.get_retry_prompt()),
                ]
                current_prompt, current_prompt_tokens = _build_chat_prompt(
                    engine,
                    retry_messages,
                    max_prompt_len,
                    tools.format_tools_for_prompt(request.tools, request.tool_choice),
                )
                continue
            break

        tool_calls = None
        finish_reason = "stop"
        content: str | None = text
        if use_tools:
            remaining, parsed = tools.parse_tool_calls(text, request.tools)
            if parsed:
                tool_calls = parsed
                finish_reason = "tool_calls"
                content = remaining or None
        elif params.stop:
            # Honor stop sequences (the runtime may not have applied them).
            truncated, hit = chat_format.truncate_at_stop(text, params.stop)
            if hit:
                content = truncated
                loop = asyncio.get_running_loop()
                completion_tokens = await loop.run_in_executor(None, engine.count_tokens, truncated)

        manager.record_request(
            engine.model_id, current_prompt_tokens, completion_tokens, time.perf_counter() - start
        )
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant", content=content, tool_calls=tool_calls
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=UsageInfo(
                prompt_tokens=current_prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=current_prompt_tokens + completion_tokens,
            ),
        )

    async def _stream_chat(engine, request, prompt, prompt_tokens, params, use_tools, req_id):
        token = request_id_var.set(req_id)
        try:
            request_id = f"chatcmpl-{uuid.uuid4().hex}"
            start = time.perf_counter()

            def chunk(delta: dict, finish_reason=None) -> str:
                payload = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
                }
                return f"data: {json.dumps(payload)}\n\n"

            full_text = ""
            finish_reason = "stop"
            stream_gen = manager.stream(engine, prompt, params)
            try:
                if use_tools:
                    # Tool detection needs the full output, so buffer then decide.
                    async for piece in stream_gen:
                        full_text += piece
                    remaining, parsed = tools.parse_tool_calls(full_text, request.tools)
                    if parsed:
                        finish_reason = "tool_calls"
                        yield chunk({"role": "assistant", "content": None})
                        for i, tc in enumerate(parsed):
                            yield chunk(
                                {
                                    "tool_calls": [
                                        {
                                            "index": i,
                                            "id": tc.id,
                                            "type": "function",
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                    ]
                                }
                            )
                    else:
                        yield chunk({"role": "assistant", "content": remaining or full_text})
                else:
                    # Real-time token streaming for normal chat, honoring stop sequences.
                    stopper = chat_format.StopStreamer(params.stop or [])
                    first = True
                    async for piece in stream_gen:
                        emit = stopper.feed(piece)
                        if emit:
                            full_text += emit
                            delta = (
                                {"role": "assistant", "content": emit}
                                if first
                                else {"content": emit}
                            )
                            first = False
                            yield chunk(delta)
                        if stopper.stopped:
                            finish_reason = "stop"
                            break
                    tail = stopper.flush()
                    if tail:
                        full_text += tail
                        yield chunk(
                            {"role": "assistant", "content": tail} if first else {"content": tail}
                        )
            except Exception as exc:  # noqa: BLE001 - report inline to the SSE client
                logger.exception("Generation failed: %s", exc)
                yield chunk({"content": f"\n\n[error: {exc}]"})
            finally:
                # Promptly stop the worker + release the model lock if the client
                # disconnected, instead of waiting for the generator to be GC'd.
                await stream_gen.aclose()

            yield chunk({}, finish_reason=finish_reason)

            loop = asyncio.get_running_loop()
            completion_tokens = await loop.run_in_executor(None, engine.count_tokens, full_text)
            manager.record_request(
                engine.model_id, prompt_tokens, completion_tokens, time.perf_counter() - start
            )

            if request.stream_options and request.stream_options.include_usage:
                usage_payload = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    },
                }
                yield f"data: {json.dumps(usage_payload)}\n\n"

            yield "data: [DONE]\n\n"
        finally:
            request_id_var.reset(token)

    # --- responses API (n8n) ----------------------------------------------

    @app.post("/v1/responses", dependencies=auth)
    async def create_response(request: ResponseRequest):
        engine = _resolve_or_400(manager, request.model)
        cfg = manager.config_for(engine.model_id)
        max_context_len = cfg.max_context_len if cfg else 2048
        max_prompt_len = cfg.max_prompt_len if cfg else 1536

        try:
            dict_messages = chat_format.responses_input_to_messages(
                request.input, request.instructions
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        prompt, prompt_tokens = chat_format.build_prompt_within_budget(
            dict_messages, engine.apply_chat_template, engine.count_tokens, max_prompt_len
        )
        params = _params_for(
            request.max_output_tokens, request.temperature, 1.0, prompt_tokens, max_context_len
        )

        response_id = f"resp-{uuid.uuid4().hex}"
        msg_id = f"msg-{uuid.uuid4().hex}"

        if request.stream:
            return StreamingResponse(
                _stream_response(
                    engine, request, prompt, prompt_tokens, params, response_id, msg_id
                ),
                media_type="text/event-stream",
            )

        start = time.perf_counter()
        result = await manager.generate(engine, prompt, params)
        manager.record_request(
            engine.model_id, prompt_tokens, result.completion_tokens, time.perf_counter() - start
        )
        return ResponseObject(
            id=response_id,
            created_at=int(time.time()),
            model=request.model,
            output=[
                ResponseOutputMessage(
                    id=msg_id,
                    content=[{"type": "output_text", "text": result.text}],
                )
            ],
        )

    async def _stream_response(engine, request, prompt, prompt_tokens, params, response_id, msg_id):
        """SSE stream for the Responses API, using OpenAI Responses event names."""
        created = int(time.time())
        start = time.perf_counter()

        def event(type_name: str, payload: dict) -> str:
            return f"event: {type_name}\ndata: {json.dumps(payload)}\n\n"

        def response_obj(text: str, status: str) -> dict:
            return {
                "id": response_id,
                "object": "response",
                "created_at": created,
                "model": request.model,
                "status": status,
                "output": [
                    {
                        "type": "message",
                        "id": msg_id,
                        "status": status,
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    }
                ],
            }

        yield event(
            "response.created",
            {"type": "response.created", "response": response_obj("", "in_progress")},
        )

        full_text = ""
        stream_gen = manager.stream(engine, prompt, params)
        try:
            async for piece in stream_gen:
                full_text += piece
                yield event(
                    "response.output_text.delta",
                    {
                        "type": "response.output_text.delta",
                        "item_id": msg_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": piece,
                    },
                )
        except Exception as exc:  # noqa: BLE001 - report inline to the SSE client
            logger.exception("Responses generation failed: %s", exc)
            yield event("response.error", {"type": "response.error", "message": str(exc)})
        finally:
            await stream_gen.aclose()

        loop = asyncio.get_running_loop()
        completion_tokens = await loop.run_in_executor(None, engine.count_tokens, full_text)
        manager.record_request(
            engine.model_id, prompt_tokens, completion_tokens, time.perf_counter() - start
        )

        yield event(
            "response.output_text.done",
            {
                "type": "response.output_text.done",
                "item_id": msg_id,
                "output_index": 0,
                "content_index": 0,
                "text": full_text,
            },
        )
        yield event(
            "response.completed",
            {"type": "response.completed", "response": response_obj(full_text, "completed")},
        )
        yield "data: [DONE]\n\n"

    return app


# Module-level app for `uvicorn app.server:app` (settings from environment).
_load_dotenv()
settings = Settings.from_env()
app = create_app(settings)


# --- CLI -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    base = Settings.from_env()

    parser = argparse.ArgumentParser(description="OpenVINO Windows LLM server")
    parser.add_argument("--model", help="Model id to auto-load on startup (from models.json)")
    parser.add_argument(
        "--device",
        help="Inference device expression, e.g. CPU, GPU, NPU, AUTO, AUTO:NPU,GPU,CPU",
    )
    parser.add_argument("--host", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, help="Bind port (default 8000)")
    parser.add_argument("--mock", action="store_true", help="Force the mock engine (no OpenVINO)")
    parser.add_argument("--list", action="store_true", help="List catalog models and exit")
    parser.add_argument(
        "--check-devices", action="store_true", help="Show OpenVINO devices and exit"
    )
    parser.add_argument(
        "--auto-convert",
        action="store_true",
        help="Auto-convert/download models on startup or load",
    )
    parser.add_argument(
        "--benchmark", action="store_true", help="Run a hardware benchmark and exit"
    )
    parser.add_argument("--benchmark-model", help="Catalog model id to benchmark")
    parser.add_argument(
        "--benchmark-devices",
        default="CPU,GPU,NPU,AUTO",
        help="Benchmark devices, e.g. CPU,GPU,NPU,AUTO or CPU;AUTO:NPU,GPU,CPU",
    )
    parser.add_argument(
        "--benchmark-runs", type=int, default=1, help="Generation runs per model/device"
    )
    parser.add_argument(
        "--benchmark-max-tokens", type=int, default=64, help="Generated token limit per run"
    )
    args = parser.parse_args(argv)

    if args.list:
        catalog = model_manager.registry.load_catalog(base.models_file)
        if not catalog:
            print("No models found. Check models.json.")
            return 0
        print("\nAvailable models:")
        print("-" * 70)
        for model_id, cfg in catalog.items():
            print(f"  {model_id:28} {cfg.name}")
            print(f"  {'':28} {cfg.description}")
            print(
                f"  {'':28} source: {cfg.source_model or '(none)'}  device: {cfg.recommended_device}"
            )
            print()
        return 0

    if args.check_devices:
        available = device_check.available_devices()
        print(f"OpenVINO available: {device_check.is_openvino_available()}")
        print(f"Devices: {', '.join(available) if available else '(none detected)'}")
        for d in device_check.device_details():
            print(f"  {d['device']}: {d['full_name']}")
        suggestions = device_check.suggested_device_targets(available)
        if suggestions:
            print("Suggested advanced targets:")
            for item in suggestions:
                suffix = " (experimental)" if item["experimental"] else ""
                print(f"  {item['device']}{suffix}: {item['note']}")
        return 0

    if args.mock:
        os.environ["OV_LLM_MOCK"] = "1"

    if args.benchmark:
        if not args.benchmark_model:
            parser.error("--benchmark requires --benchmark-model")
        from runtime import benchmark_runner

        bench_args = [
            "--benchmark-model",
            args.benchmark_model,
            "--benchmark-devices",
            args.benchmark_devices,
            "--runs",
            str(args.benchmark_runs),
            "--max-tokens",
            str(args.benchmark_max_tokens),
        ]
        if args.mock:
            bench_args.append("--mock")
        return benchmark_runner.main(bench_args)

    if args.device is not None:
        try:
            device = device_check.validate_device_expression(args.device)
        except device_check.DeviceValidationError as exc:
            parser.error(str(exc))
    else:
        device = None

    overrides = {
        "device": device,
        "host": args.host,
        "port": args.port,
        "default_model": args.model,
        "force_mock": True if args.mock else None,
        "auto_convert": True if args.auto_convert else None,
    }
    resolved = base.replace(**overrides)

    import uvicorn

    logger.info("Visit http://localhost:%d", resolved.port)
    if resolved.host == "0.0.0.0":
        logger.warning(
            "Binding to 0.0.0.0 exposes the server on your LAN. Use a trusted network only."
        )

    uvicorn.run(create_app(resolved), host=resolved.host, port=resolved.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
