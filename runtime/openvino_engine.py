"""Inference engine wrappers.

``OpenVINOEngine`` wraps ``openvino_genai.LLMPipeline`` (imported lazily).
``MockEngine`` produces canned, streamed responses so the full server and web UI
can be exercised on machines without OpenVINO (e.g. macOS during frontend work).

Both expose the same small interface:
    apply_chat_template(messages, add_generation_prompt) -> str
    count_tokens(text) -> int
    generate(prompt, params) -> GenResult
    stream(prompt, params) -> StreamHandle
"""

from __future__ import annotations

import contextlib
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app import chat_format
from runtime.device_check import is_openvino_available, normalize_device

logger = logging.getLogger("ov-llm.engine")

_SENTINEL = object()


@dataclass
class GenParams:
    max_new_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 1.0
    do_sample: bool = True
    seed: int | None = None
    stop: list[str] | None = None


@dataclass
class GenResult:
    text: str
    completion_tokens: int


class StreamHandle:
    """Thread-safe bridge from a synchronous generation worker to the caller.

    The worker thread calls :meth:`push` / :meth:`finish`; the consumer calls
    :meth:`next_chunk` (designed to be run via ``run_in_executor`` so the asyncio
    event loop is never blocked). ``next_chunk`` returns ``None`` at end of stream.
    """

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue(maxsize=1024)
        self.error: BaseException | None = None
        self.text = ""
        self._stop = threading.Event()
        self._done = threading.Event()

    def push(self, piece: str) -> None:
        self.text += piece
        self._q.put(piece)

    def finish(self, error: BaseException | None = None) -> None:
        self.error = error
        self._q.put(_SENTINEL)
        self._done.set()

    def next_chunk(self) -> str | None:
        item = self._q.get()
        return None if item is _SENTINEL else item

    def request_stop(self) -> None:
        """Ask the worker to stop generating early (e.g. the client disconnected)."""
        self._stop.set()

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def wait_closed(self, timeout: float | None = 30.0) -> None:
        """Block until the worker thread has finished, so the engine is free again."""
        self._done.wait(timeout)


class BaseEngine:
    backend = "base"
    model_id: str = ""
    model_path: str = ""
    device: str = "CPU"

    def apply_chat_template(self, messages: list[dict], add_generation_prompt: bool = True) -> str:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        raise NotImplementedError

    def generate(self, prompt: str, params: GenParams) -> GenResult:
        raise NotImplementedError

    def stream(self, prompt: str, params: GenParams) -> StreamHandle:
        raise NotImplementedError

    def close(self) -> None:  # noqa: B027 - intentional no-op default
        pass


# --- Mock engine -----------------------------------------------------------


class MockEngine(BaseEngine):
    """A dependency-free engine that streams a canned reply. For UI/API testing."""

    backend = "mock"

    def __init__(self, model_id: str, model_path: str = "", device: str = "MOCK") -> None:
        self.model_id = model_id
        self.model_path = str(model_path)
        self.device = device

    def apply_chat_template(self, messages: list[dict], add_generation_prompt: bool = True) -> str:
        return chat_format.render_chatml(messages, add_generation_prompt)

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _reply(self, prompt: str) -> str:
        matches = re.findall(r"<\|im_start\|>user\n(.*?)<\|im_end\|>", prompt, re.DOTALL)
        last_user = matches[-1].strip() if matches else "(no user message found)"
        return (
            "**Mock engine** — OpenVINO is not active, so this is a canned response.\n\n"
            f"You said: _{last_user[:400]}_\n\n"
            "This lets you exercise the full chat UI, streaming, tokens, and the OpenAI API on any "
            "machine. On Windows with OpenVINO installed and a converted model, you'll get real "
            f"output instead.\n\n```python\nprint('hello from {self.model_id}')\n```"
        )

    def generate(self, prompt: str, params: GenParams) -> GenResult:
        text = self._reply(prompt)
        return GenResult(text=text, completion_tokens=self.count_tokens(text))

    def stream(self, prompt: str, params: GenParams) -> StreamHandle:
        handle = StreamHandle()
        text = self._reply(prompt)

        def worker() -> None:
            for token in re.findall(r"\S+\s*", text):
                if handle.should_stop():
                    break
                time.sleep(0.015)  # simulate generation latency for the UI
                handle.push(token)
            handle.finish()

        threading.Thread(target=worker, daemon=True).start()
        return handle


# --- OpenVINO GenAI engine -------------------------------------------------


class OpenVINOEngine(BaseEngine):
    """Wraps ``openvino_genai.LLMPipeline``. Constructed only when OpenVINO exists."""

    backend = "openvino-genai"

    def __init__(
        self,
        model_id: str,
        model_path: str,
        device: str,
        plugin_config: dict | None = None,
    ) -> None:
        import openvino_genai as ov_genai  # lazy: only imported on a real load

        self._ov = ov_genai
        self.model_id = model_id
        self.model_path = str(model_path)
        self.device = normalize_device(device)
        self._closed = False

        config = dict(plugin_config or {})
        logger.info("Loading '%s' on %s from %s", model_id, self.device, self.model_path)
        if config:
            self._pipe = ov_genai.LLMPipeline(self.model_path, self.device, **config)
        else:
            self._pipe = ov_genai.LLMPipeline(self.model_path, self.device)
        self._tokenizer = self._pipe.get_tokenizer()
        logger.info("Model '%s' ready on %s", model_id, self.device)

    def _check_closed(self) -> None:
        if self._closed:
            raise RuntimeError(f"Engine for '{self.model_id}' is closed")

    def apply_chat_template(self, messages: list[dict], add_generation_prompt: bool = True) -> str:
        self._check_closed()
        try:
            try:
                return self._tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=add_generation_prompt,
                )
            except TypeError:
                return self._tokenizer.apply_chat_template(messages, add_generation_prompt)
        except Exception as exc:  # model has no chat template, or signature differs
            logger.debug("apply_chat_template failed (%s); falling back to ChatML", exc)
            return chat_format.render_chatml(messages, add_generation_prompt)

    def count_tokens(self, text: str) -> int:
        self._check_closed()
        try:
            ids = self._tokenizer.encode(text).input_ids
            try:
                return int(ids.get_shape()[-1])
            except Exception:
                return int(ids.shape[-1])
        except Exception:
            return max(1, len(text) // 4)

    def _build_config(self, params: GenParams):
        cfg = self._ov.GenerationConfig()
        cfg.max_new_tokens = int(params.max_new_tokens)
        if params.do_sample and params.temperature and params.temperature > 0:
            cfg.do_sample = True
            cfg.temperature = float(params.temperature)
            cfg.top_p = float(params.top_p)
            if params.seed is not None:
                # Attribute name varies across OpenVINO GenAI versions; best effort.
                with contextlib.suppress(Exception):
                    cfg.rng_seed = int(params.seed)
        else:
            cfg.do_sample = False
        if params.stop:
            # Let the runtime stop early when supported; the server also truncates
            # defensively so correctness never depends on this attribute existing.
            with contextlib.suppress(Exception):
                cfg.stop_strings = set(params.stop)
                cfg.include_stop_str_in_output = False
        return cfg

    def generate(self, prompt: str, params: GenParams) -> GenResult:
        self._check_closed()
        result = self._pipe.generate(prompt, self._build_config(params))
        text = _result_text(result)
        return GenResult(text=text, completion_tokens=self.count_tokens(text))

    def stream(self, prompt: str, params: GenParams) -> StreamHandle:
        self._check_closed()
        handle = StreamHandle()
        cfg = self._build_config(params)
        pipe = self._pipe

        def streamer(subword: str) -> bool:
            handle.push(subword)
            return handle.should_stop()  # True => stop generation, False => keep going

        def worker() -> None:
            try:
                pipe.generate(prompt, cfg, streamer)
            except BaseException as exc:  # noqa: BLE001 - surface to the consumer
                handle.finish(error=exc)
                return
            handle.finish()

        threading.Thread(target=worker, daemon=True).start()
        return handle

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        logger.info("Closing engine for '%s'", self.model_id)
        self._pipe = None
        self._tokenizer = None


def _result_text(result) -> str:
    """Extract generated text from an ov_genai result, defensively."""
    try:
        if hasattr(result, "texts") and result.texts:
            return str(result.texts[0])
    except Exception:
        pass
    return str(result)


# --- Factory ---------------------------------------------------------------


def build_plugin_config(
    device: str,
    max_prompt_len: int | None,
    cache_dir: str | Path | None = None,
) -> dict:
    """Device-specific OpenVINO plugin config.

    The NPU plugin compiles to static shapes and benefits from an explicit prompt
    length bound. Composite targets such as ``AUTO:NPU,GPU,CPU`` intentionally
    use OpenVINO GenAI defaults because plugin-option behavior can differ across
    routed devices.
    """
    device = normalize_device(device)
    config: dict = {}
    if device == "NPU" and max_prompt_len:
        config["MAX_PROMPT_LEN"] = int(max_prompt_len)

    if cache_dir:
        try:
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            config["CACHE_DIR"] = str(cache_path)
        except Exception as exc:
            logger.warning("Failed to create cache directory '%s': %s", cache_dir, exc)

    return config


def create_engine(
    *,
    model_id: str,
    model_path: str,
    device: str,
    max_prompt_len: int | None = None,
    force_mock: bool = False,
    cache_dir: str | Path | None = None,
) -> BaseEngine:
    """Create the appropriate engine for the current environment.

    Falls back to :class:`MockEngine` when OpenVINO is unavailable or mock mode is
    forced, so the server stays usable for frontend/API work everywhere.
    """
    device = normalize_device(device)
    if force_mock or not is_openvino_available():
        reason = "forced" if force_mock else "OpenVINO not installed"
        logger.info("Using MOCK engine for '%s' (%s)", model_id, reason)
        return MockEngine(model_id, model_path, device if force_mock else "MOCK")

    plugin_config = build_plugin_config(device, max_prompt_len, cache_dir)
    return OpenVINOEngine(model_id, model_path, device, plugin_config)
