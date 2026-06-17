"""FastAPI entry point: OpenAI-compatible routes, lifecycle, and the CLI.

Run via the CLI:
    python -m app.server --model tinyllama-1.1b-chat --device CPU
Or via uvicorn directly (settings come from environment variables):
    uvicorn app.server:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app import chat_format, model_manager, tools
from app.config import BASE_DIR, VALID_DEVICES, Settings
from app.openai_api import (
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatMessage,
    ModelDeleteRequest,
    ModelLoadRequest,
    ModelUnloadRequest,
    ResponseObject,
    ResponseOutputMessage,
    ResponseRequest,
    UsageInfo,
)
from app.telemetry import cpu_stats, disk_stats, memory_stats
from runtime import device_check
from runtime.openvino_engine import BaseEngine, GenParams

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ov-llm.server")

WEB_DIR = BASE_DIR / "web"


def _load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded environment from %s", env_path)


# --- Generation helpers ----------------------------------------------------


def _params_for(request_max_tokens: int | None, temperature: float | None, top_p: float | None,
                prompt_tokens: int, max_context_len: int) -> GenParams:
    available = max(max_context_len - prompt_tokens - 8, 16)
    requested = request_max_tokens or 512
    max_new = max(min(requested, available), 16)
    temp = 0.7 if temperature is None else float(temperature)
    return GenParams(
        max_new_tokens=max_new,
        temperature=temp,
        top_p=1.0 if top_p is None else float(top_p),
        do_sample=temp > 0,
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

    app = FastAPI(title="OpenVINO Windows LLM", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.manager = manager

    # --- auth (optional) ---------------------------------------------------

    def require_api_key(authorization: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        if authorization != f"Bearer {settings.api_key}":
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    auth = [Depends(require_api_key)]

    # --- UI + health -------------------------------------------------------

    @app.get("/", response_class=FileResponse)
    async def index():
        return FileResponse(
            WEB_DIR / "index.html",
            headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
        )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "mock": manager.force_mock,
            "device": settings.device,
            "openvino": device_check.is_openvino_available(),
            "models_loaded": len(manager.engines),
        }

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

    @app.post("/v1/models/load", dependencies=auth)
    async def load_model(req: ModelLoadRequest):
        if req.model not in manager.catalog:
            raise HTTPException(status_code=404, detail=f"Unknown model '{req.model}'")
        if req.device and device_check.normalize_device(req.device) not in VALID_DEVICES:
            raise HTTPException(status_code=400, detail=f"Invalid device '{req.device}'")

        task = manager.schedule_load(req.model, req.device)
        entry = manager.catalog_entry(req.model)
        if task is None and entry["is_loaded"]:
            return {"status": "loaded", "message": f"{entry['name']} is already loaded.", "model": entry}
        return {
            "status": entry["status"],
            "message": f"Loading {entry['name']}. First load can take a while.",
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
            result = manager.delete(req.model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc

        entry = manager.catalog_entry(req.model)
        freed_gb = round(result["freed_bytes"] / (1024**3), 2)
        if not result["deleted"]:
            return {"status": "noop", "message": f"No local files for {entry['name']}.", "freed_gb": 0.0, "model": entry}
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
        return {
            "default_device": settings.device,
            "openvino_available": device_check.is_openvino_available(),
            "mock": manager.force_mock,
            "devices": device_check.device_details(),
        }

    @app.get("/v1/system/status", dependencies=auth)
    async def system_status():
        entries = manager.catalog_entries()
        return {
            "memory": memory_stats(),
            "cpu": cpu_stats(),
            "device": {
                "default": settings.device,
                "mock": manager.force_mock,
                "available": device_check.available_devices(),
                "busy": manager.any_busy(),
            },
            "models": {
                "loaded": list(manager.engines.keys()),
                "count": len(manager.engines),
                "loading_count": manager.loading_count(),
                "available": entries,
            },
            "disk": disk_stats(settings.models_dir),
        }

    # --- chat completions --------------------------------------------------

    @app.post("/v1/chat/completions", dependencies=auth)
    async def chat_completions(request: ChatCompletionRequest):
        engine = _resolve_or_400(manager, request.model)
        cfg = manager.config_for(engine.model_id)
        max_context_len = cfg.max_context_len if cfg else 2048
        max_prompt_len = cfg.max_prompt_len if cfg else 1536

        use_tools = bool(request.tools) and request.tool_choice != "none"
        system_override = tools.format_tools_for_prompt(request.tools, request.tool_choice) if use_tools else ""

        prompt, prompt_tokens = _build_chat_prompt(
            engine, request.messages, max_prompt_len, system_override
        )
        params = _params_for(
            request.max_tokens, request.temperature, request.top_p, prompt_tokens, max_context_len
        )

        if request.stream:
            return StreamingResponse(
                _stream_chat(engine, request, prompt, prompt_tokens, params, use_tools),
                media_type="text/event-stream",
            )
        return await _complete_chat(engine, request, prompt, prompt_tokens, params, use_tools, max_prompt_len)

    async def _complete_chat(engine, request, prompt, prompt_tokens, params, use_tools, max_prompt_len):
        MAX_RETRIES = 2
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
                    engine, retry_messages, max_prompt_len,
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

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=content, tool_calls=tool_calls),
                    finish_reason=finish_reason,
                )
            ],
            usage=UsageInfo(
                prompt_tokens=current_prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=current_prompt_tokens + completion_tokens,
            ),
        )

    async def _stream_chat(engine, request, prompt, prompt_tokens, params, use_tools):
        request_id = f"chatcmpl-{uuid.uuid4().hex}"

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
                                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                                    }
                                ]
                            }
                        )
                else:
                    yield chunk({"role": "assistant", "content": remaining or full_text})
            else:
                # Real-time token streaming for normal chat.
                first = True
                async for piece in stream_gen:
                    full_text += piece
                    delta = {"content": piece}
                    if first:
                        delta = {"role": "assistant", "content": piece}
                        first = False
                    yield chunk(delta)
        except Exception as exc:  # noqa: BLE001 - report inline to the SSE client
            logger.exception("Generation failed: %s", exc)
            yield chunk({"content": f"\n\n[error: {exc}]"})
        finally:
            # Promptly stop the worker + release the model lock if the client
            # disconnected, instead of waiting for the generator to be GC'd.
            await stream_gen.aclose()

        yield chunk({}, finish_reason=finish_reason)

        if request.stream_options and request.stream_options.include_usage:
            loop = asyncio.get_running_loop()
            completion_tokens = await loop.run_in_executor(None, engine.count_tokens, full_text)
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

    # --- responses API (n8n) ----------------------------------------------

    @app.post("/v1/responses", dependencies=auth)
    async def create_response(request: ResponseRequest):
        engine = _resolve_or_400(manager, request.model)
        cfg = manager.config_for(engine.model_id)
        max_context_len = cfg.max_context_len if cfg else 2048
        max_prompt_len = cfg.max_prompt_len if cfg else 1536

        try:
            dict_messages = chat_format.responses_input_to_messages(request.input, request.instructions)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        prompt, prompt_tokens = chat_format.build_prompt_within_budget(
            dict_messages, engine.apply_chat_template, engine.count_tokens, max_prompt_len
        )
        params = _params_for(
            request.max_output_tokens, request.temperature, 1.0, prompt_tokens, max_context_len
        )
        result = await manager.generate(engine, prompt, params)

        return ResponseObject(
            id=f"resp-{uuid.uuid4().hex}",
            created_at=int(time.time()),
            model=request.model,
            output=[
                ResponseOutputMessage(
                    id=f"msg-{uuid.uuid4().hex}",
                    content=[{"type": "output_text", "text": result.text}],
                )
            ],
        )

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
    parser.add_argument("--device", choices=list(VALID_DEVICES), help="Inference device")
    parser.add_argument("--host", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, help="Bind port (default 8000)")
    parser.add_argument("--mock", action="store_true", help="Force the mock engine (no OpenVINO)")
    parser.add_argument("--list", action="store_true", help="List catalog models and exit")
    parser.add_argument("--check-devices", action="store_true", help="Show OpenVINO devices and exit")
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
            print(f"  {'':28} source: {cfg.source_model or '(none)'}  device: {cfg.recommended_device}")
            print()
        return 0

    if args.check_devices:
        available = device_check.available_devices()
        print(f"OpenVINO available: {device_check.is_openvino_available()}")
        print(f"Devices: {', '.join(available) if available else '(none detected)'}")
        for d in device_check.device_details():
            print(f"  {d['device']}: {d['full_name']}")
        return 0

    if args.mock:
        os.environ["OV_LLM_MOCK"] = "1"

    overrides = {
        "device": device_check.normalize_device(args.device) if args.device else None,
        "host": args.host,
        "port": args.port,
        "default_model": args.model,
        "force_mock": True if args.mock else None,
    }
    resolved = base.replace(**overrides)

    import uvicorn

    logger.info("Visit http://localhost:%d", resolved.port)
    if resolved.host == "0.0.0.0":
        logger.warning("Binding to 0.0.0.0 exposes the server on your LAN. Use a trusted network only.")

    uvicorn.run(create_app(resolved), host=resolved.host, port=resolved.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
