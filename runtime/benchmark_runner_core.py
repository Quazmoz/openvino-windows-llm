"""Hardware benchmark runner and local result store.

The runner intentionally uses :class:`app.model_manager.ModelManager` and the
shared :class:`runtime.openvino_engine.BaseEngine` interface, so API and CLI
benchmarks exercise the same prompt formatting, device validation, engine
factory, and streaming bridge as normal chat serving.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import chat_format
from app.config import Settings
from app.model_manager import ModelManager
from runtime import device_check
from runtime.openvino_engine import BaseEngine, GenParams

DEFAULT_BENCHMARK_PROMPT = (
    "You are running a local hardware benchmark. Reply with two concise bullet "
    "points about why measuring this exact machine matters."
)
DEFAULT_BENCHMARK_DEVICES = ("CPU", "GPU", "NPU", "AUTO")
BENCHMARK_CAVEAT = (
    "AUTO, MULTI, and HETERO are OpenVINO routing modes. This score reflects "
    "only the measured run and is not a general speed guarantee."
)


@dataclass
class BenchmarkResult:
    run_id: str
    model_id: str
    requested_device: str
    actual_device: str | None
    load_time_ms: float | None
    time_to_first_token_ms: float | None
    total_latency_ms: float | None
    prompt_tokens: int
    completion_tokens: int
    tokens_sec: float | None
    success: bool
    error: str | None
    timestamp: str
    runs: int = 1
    score: float | None = None


@dataclass
class ContextDepthResult:
    """Certification-safe facts for one deterministic context-depth trial."""

    model_id: str
    requested_device: str
    actual_device: str | None
    requested_context: int
    prompt_tokens: int
    tokens_generated: int
    passed: bool
    error: str | None
    timestamp: str


class BenchmarkStore:
    """Small JSON-backed store for benchmark runs."""

    def __init__(self, path: str | Path, *, max_runs: int = 100) -> None:
        self.path = Path(path)
        self.max_runs = max_runs
        self._lock = threading.Lock()

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._read()["runs"])

    def latest(self) -> dict[str, Any] | None:
        runs = self.list_runs()
        return runs[-1] if runs else None

    def append(self, run: dict[str, Any]) -> None:
        with self._lock:
            data = self._read()
            data["runs"].append(run)
            if self.max_runs > 0:
                data["runs"] = data["runs"][-self.max_runs :]
            self._write(data)

    def clear(self) -> int:
        with self._lock:
            count = len(self._read()["runs"])
            self._write({"schema_version": 1, "runs": []})
            return count

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "runs": []}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"schema_version": 1, "runs": []}
        if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
            return {"schema_version": 1, "runs": []}
        return {"schema_version": int(data.get("schema_version", 1)), "runs": data["runs"]}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)


async def run_benchmark_suite(
    manager: ModelManager,
    *,
    model_ids: list[str],
    devices: list[str],
    prompt: str = DEFAULT_BENCHMARK_PROMPT,
    max_tokens: int = 64,
    runs: int = 1,
) -> dict[str, Any]:
    """Run every requested model/device combination and return one persisted run."""

    run_id = f"bench-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    started_at = _utc_now()
    normalized_devices = [device_check.validate_device_expression(device) for device in devices]
    results: list[dict[str, Any]] = []

    for model_id in _dedupe(model_ids):
        for device in normalized_devices:
            result = await benchmark_model_device(
                manager,
                run_id=run_id,
                model_id=model_id,
                device=device,
                prompt=prompt,
                max_tokens=max_tokens,
                runs=runs,
            )
            results.append(asdict(result))

    recommendation = score_benchmark_results(results, mock=manager.force_mock)
    return {
        "run_id": run_id,
        "created_at": started_at,
        "finished_at": _utc_now(),
        "prompt": prompt,
        "max_tokens": max_tokens,
        "runs_per_combo": runs,
        "mock": manager.force_mock,
        "results": results,
        "recommendation": recommendation,
        "caveat": BENCHMARK_CAVEAT,
    }


async def benchmark_model_device(
    manager: ModelManager,
    *,
    run_id: str,
    model_id: str,
    device: str,
    prompt: str,
    max_tokens: int,
    runs: int,
) -> BenchmarkResult:
    """Benchmark one model/device pair, continuing failures as result rows."""

    timestamp = _utc_now()
    engine: BaseEngine | None = None
    load_time_ms: float | None = None
    prompt_tokens = 0
    try:
        engine, load_time_s = await manager.build_temporary_engine(model_id, device)
        load_time_ms = _ms(load_time_s)
        cfg = manager.config_for(model_id)
        max_prompt_len = cfg.max_prompt_len if cfg else 1536
        max_context_len = cfg.max_context_len if cfg else 2048

        loop = asyncio.get_running_loop()
        prompt_text, prompt_tokens = await loop.run_in_executor(
            None, _build_benchmark_prompt, engine, prompt, max_prompt_len
        )
        max_new_tokens = min(int(max_tokens), max(max_context_len - prompt_tokens - 8, 1))
        params = GenParams(
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            top_p=1.0,
            do_sample=False,
        )

        generations = [
            await _stream_generation_once(engine, prompt_text, params)
            for _ in range(max(int(runs), 1))
        ]
        completion_tokens_values = [item["completion_tokens"] for item in generations]
        total_completion_tokens = sum(completion_tokens_values)
        total_latency_s = sum(item["latency_s"] for item in generations)
        ttft_values = [item["ttft_s"] for item in generations if item["ttft_s"] is not None]

        completion_tokens = round(total_completion_tokens / len(generations))
        total_latency_ms = _ms(total_latency_s / len(generations))
        ttft_ms = _ms(sum(ttft_values) / len(ttft_values)) if ttft_values else None
        tokens_sec = (
            round(total_completion_tokens / total_latency_s, 3) if total_latency_s > 0 else None
        )

        return BenchmarkResult(
            run_id=run_id,
            model_id=model_id,
            requested_device=device,
            actual_device=_reported_actual_device(engine, device),
            load_time_ms=load_time_ms,
            time_to_first_token_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_sec=tokens_sec,
            success=True,
            error=None,
            timestamp=timestamp,
            runs=runs,
        )
    except Exception as exc:  # noqa: BLE001 - benchmark rows should capture failures
        return BenchmarkResult(
            run_id=run_id,
            model_id=model_id,
            requested_device=device,
            actual_device=_reported_actual_device(engine, device) if engine else None,
            load_time_ms=load_time_ms,
            time_to_first_token_ms=None,
            total_latency_ms=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            tokens_sec=None,
            success=False,
            error=str(exc),
            timestamp=timestamp,
            runs=runs,
            score=-25.0,
        )
    finally:
        if engine is not None:
            with contextlib.suppress(Exception):
                engine.close()


async def certify_context_depth(
    manager: ModelManager,
    *,
    model_id: str,
    device: str,
    requested_context: int,
) -> ContextDepthResult:
    """Generate one token after a deterministic prompt of the requested depth.

    This is a functional context-capacity check, not a performance benchmark.
    A pass requires an exact prompt token count, successful generation, and an
    actual device consistent with the requested direct device.
    """

    timestamp = _utc_now()
    engine: BaseEngine | None = None
    prompt_tokens = 0
    actual_device: str | None = None
    try:
        cfg = manager.config_for(model_id)
        if cfg is None:
            raise ValueError(f"Unknown model '{model_id}'.")
        if requested_context < 1 or requested_context > cfg.max_prompt_len:
            raise ValueError(
                f"Requested context must be between 1 and {cfg.max_prompt_len} prompt tokens."
            )
        normalized_device = device_check.validate_device_expression(device)
        engine, _ = await manager.build_temporary_engine(model_id, normalized_device)
        actual_device = _reported_actual_device(engine, normalized_device)
        loop = asyncio.get_running_loop()
        prompt, prompt_tokens = await loop.run_in_executor(
            None, _build_exact_context_prompt, engine, requested_context
        )
        if prompt_tokens != requested_context:
            raise RuntimeError(
                f"Tokenizer could not construct exactly {requested_context} prompt tokens; "
                f"constructed {prompt_tokens}."
            )
        generation = await _stream_generation_once(
            engine,
            prompt,
            GenParams(max_new_tokens=1, temperature=0.0, top_p=1.0, do_sample=False),
        )
        tokens_generated = int(generation["completion_tokens"])
        if tokens_generated < 1:
            raise RuntimeError("Generation completed without producing a token.")
        if not _device_matches_request(normalized_device, actual_device):
            raise RuntimeError(
                f"Requested device {normalized_device} but runtime reported "
                f"{actual_device or 'unknown'}."
            )
        return ContextDepthResult(
            model_id=model_id,
            requested_device=normalized_device,
            actual_device=actual_device,
            requested_context=requested_context,
            prompt_tokens=prompt_tokens,
            tokens_generated=tokens_generated,
            passed=True,
            error=None,
            timestamp=timestamp,
        )
    except Exception as exc:  # noqa: BLE001 - certification retains a failed result
        return ContextDepthResult(
            model_id=model_id,
            requested_device=device,
            actual_device=actual_device,
            requested_context=requested_context,
            prompt_tokens=prompt_tokens,
            tokens_generated=0,
            passed=False,
            error=str(exc),
            timestamp=timestamp,
        )
    finally:
        if engine is not None:
            with contextlib.suppress(Exception):
                engine.close()


def score_benchmark_results(results: list[dict[str, Any]], *, mock: bool = False) -> dict[str, Any]:
    """Assign balanced scores and choose a practical recommendation.

    Successful runs are always ranked ahead of failed runs. Within successful
    rows, the score favors high tokens/sec, low first-token latency, low total
    latency, and modest load time, with an explicit penalty once load time is
    very high.
    """

    successes = [r for r in results if r.get("success")]
    if not successes:
        for result in results:
            result["score"] = float(result.get("score") or -25.0)
        return {
            "model_id": None,
            "requested_device": None,
            "actual_device": None,
            "score": 0.0,
            "summary": "No successful benchmark run completed.",
            "rationale": ["Every requested model/device combination returned an error."],
            "caveat": BENCHMARK_CAVEAT,
        }

    max_tps = max(_positive(r.get("tokens_sec")) for r in successes) or 1.0
    min_ttft = min(_latency_for_ttft(r) for r in successes)
    min_total = min(_positive(r.get("total_latency_ms")) for r in successes) or 1.0
    min_load = min(max(_positive(r.get("load_time_ms")), 1.0) for r in successes)

    for result in results:
        if not result.get("success"):
            result["score"] = -25.0
            continue

        tps_norm = _positive(result.get("tokens_sec")) / max_tps
        ttft_norm = min_ttft / _latency_for_ttft(result)
        total_norm = min_total / (_positive(result.get("total_latency_ms")) or min_total)
        load_ms = max(_positive(result.get("load_time_ms")), 1.0)
        load_norm = min_load / load_ms
        high_load_penalty = 0.0
        if load_ms > 30_000:
            high_load_penalty = min((load_ms - 30_000) / 90_000, 1.0) * 0.20

        score = (0.50 * tps_norm) + (0.30 * ttft_norm) + (0.10 * total_norm) + (0.10 * load_norm)
        score = max(0.0, (score - high_load_penalty) * 100)
        result["score"] = round(score, 2)

    best = max(successes, key=lambda item: float(item.get("score") or 0.0))
    summary_prefix = (
        "Mock benchmark completed; rerun on Windows with OpenVINO hardware for a real device recommendation."
        if mock
        else f"Recommended {best['model_id']} on {best['requested_device']} from this benchmark run."
    )
    return {
        "model_id": best["model_id"],
        "requested_device": best["requested_device"],
        "actual_device": best.get("actual_device"),
        "score": best.get("score"),
        "summary": summary_prefix,
        "rationale": [
            f"{best['tokens_sec']:.2f} tokens/sec"
            if best.get("tokens_sec")
            else "Tokens/sec was unavailable.",
            (
                f"{best['time_to_first_token_ms']:.1f} ms first-token latency"
                if best.get("time_to_first_token_ms") is not None
                else "First-token latency was not measurable for this backend."
            ),
            (
                f"{best['load_time_ms']:.1f} ms load time"
                if best.get("load_time_ms") is not None
                else "Load time was unavailable."
            ),
        ],
        "caveat": BENCHMARK_CAVEAT,
    }


def split_device_targets(raw: str) -> list[str]:
    """Split a CLI/UI device list while preserving commas inside META targets."""

    if ";" in raw:
        candidates = [part.strip() for part in raw.split(";")]
    else:
        tokens = [part.strip() for part in raw.split(",")]
        candidates: list[str] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if ":" in token:
                parts = [token]
                i += 1
                while i < len(tokens) and ":" not in tokens[i]:
                    parts.append(tokens[i])
                    i += 1
                candidates.append(",".join(parts))
            else:
                candidates.append(token)
                i += 1

    devices: list[str] = []
    for candidate in candidates:
        if not candidate:
            raise device_check.DeviceValidationError("Device list contains an empty entry.")
        devices.append(device_check.validate_device_expression(candidate))
    return devices


def _build_benchmark_prompt(
    engine: BaseEngine,
    prompt: str,
    max_prompt_len: int,
) -> tuple[str, int]:
    messages = [{"role": "user", "content": prompt}]
    return chat_format.build_prompt_within_budget(
        messages, engine.apply_chat_template, engine.count_tokens, max_prompt_len
    )


def _build_exact_context_prompt(
    engine: BaseEngine,
    requested_context: int,
) -> tuple[str, int]:
    """Construct a deterministic chat prompt with an exact tokenizer count."""

    def render(characters: int) -> tuple[str, int]:
        messages = [{"role": "user", "content": "x" * characters}]
        prompt = engine.apply_chat_template(messages, add_generation_prompt=True)
        return prompt, engine.count_tokens(prompt)

    low = 0
    high = max(requested_context * 8, 64)
    while render(high)[1] < requested_context:
        high *= 2
        if high > requested_context * 256:
            break
    while low <= high:
        middle = (low + high) // 2
        _, count = render(middle)
        if count < requested_context:
            low = middle + 1
        elif count > requested_context:
            high = middle - 1
        else:
            return render(middle)
    candidates = [render(value) for value in range(max(high - 32, 0), low + 33)]
    exact = next((candidate for candidate in candidates if candidate[1] == requested_context), None)
    if exact is not None:
        return exact
    return max(
        (candidate for candidate in candidates if candidate[1] <= requested_context),
        key=lambda candidate: candidate[1],
        default=render(0),
    )


async def _stream_generation_once(
    engine: BaseEngine,
    prompt: str,
    params: GenParams,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    started = time.perf_counter()
    first_token_at: float | None = None
    pieces: list[str] = []
    handle = engine.stream(prompt, params)
    try:
        while True:
            piece = await loop.run_in_executor(None, handle.next_chunk)
            if piece is None:
                break
            if first_token_at is None and piece:
                first_token_at = time.perf_counter()
            pieces.append(piece)
        if handle.error is not None:
            raise handle.error
    finally:
        handle.request_stop()
        await loop.run_in_executor(None, handle.wait_closed)

    latency_s = time.perf_counter() - started
    text = "".join(pieces)
    completion_tokens = await loop.run_in_executor(None, engine.count_tokens, text)
    return {
        "ttft_s": None if first_token_at is None else first_token_at - started,
        "latency_s": latency_s,
        "completion_tokens": completion_tokens,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 3)


def _positive(value: Any) -> float:
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _latency_for_ttft(result: dict[str, Any]) -> float:
    value = result.get("time_to_first_token_ms")
    if value is None:
        value = result.get("total_latency_ms")
    return max(_positive(value), 1.0)


def _reported_actual_device(engine: BaseEngine, requested_device: str) -> str | None:
    actual = getattr(engine, "actual_device", None)
    if actual:
        return str(actual)
    engine_device = getattr(engine, "device", None)
    if not engine_device:
        return None
    try:
        parsed = device_check.parse_device_expression(requested_device)
    except device_check.DeviceValidationError:
        return str(engine_device)
    if parsed.kind in {"AUTO", "MULTI", "HETERO"}:
        return None if str(engine_device) == requested_device else str(engine_device)
    return str(engine_device)


def _device_matches_request(requested_device: str, actual_device: str | None) -> bool:
    if not actual_device:
        return False
    parsed = device_check.parse_device_expression(requested_device)
    if parsed.kind in {"AUTO", "MULTI", "HETERO"}:
        return True
    return actual_device.split(".", 1)[0].upper() == parsed.kind


def _print_table(run: dict[str, Any]) -> None:
    headers = [
        "model",
        "device",
        "status",
        "load_ms",
        "ttft_ms",
        "latency_ms",
        "tokens",
        "tok/s",
        "score",
    ]
    rows = []
    for result in run["results"]:
        rows.append(
            [
                result["model_id"],
                result["requested_device"],
                "ok" if result["success"] else "fail",
                _fmt(result.get("load_time_ms")),
                _fmt(result.get("time_to_first_token_ms")),
                _fmt(result.get("total_latency_ms")),
                str(result.get("completion_tokens") or 0),
                _fmt(result.get("tokens_sec")),
                _fmt(result.get("score")),
            ]
        )
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], min(len(cell), 48))

    def line(values: list[str]) -> str:
        clipped = [value if len(value) <= 48 else value[:45] + "..." for value in values]
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(clipped))

    print(line(headers))
    print(line(["-" * width for width in widths]))
    for row in rows:
        print(line(row))


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


async def _main_async(args: argparse.Namespace) -> int:
    settings = Settings.from_env().replace(
        default_model=None,
        force_mock=True if args.mock else None,
        benchmark_results_file=args.output or None,
    )
    manager = ModelManager(settings)
    devices = split_device_targets(args.benchmark_devices)
    run = await run_benchmark_suite(
        manager,
        model_ids=[args.benchmark_model],
        devices=devices,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        runs=args.runs,
    )
    BenchmarkStore(settings.benchmark_results_file).append(run)
    _print_table(run)
    rec = run["recommendation"]
    print()
    print(rec["summary"])
    print(rec["caveat"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark catalog models across OpenVINO devices."
    )
    parser.add_argument(
        "--benchmark-model", required=True, help="Catalog model id from models.json"
    )
    parser.add_argument(
        "--benchmark-devices",
        default=",".join(DEFAULT_BENCHMARK_DEVICES),
        help="Device targets, e.g. CPU,GPU,NPU,AUTO or CPU;AUTO:NPU,GPU,CPU",
    )
    parser.add_argument(
        "--prompt", default=DEFAULT_BENCHMARK_PROMPT, help="Prompt used for every run"
    )
    parser.add_argument("--max-tokens", type=int, default=64, help="Generated token limit per run")
    parser.add_argument("--runs", type=int, default=1, help="Generation runs per model/device")
    parser.add_argument(
        "--mock", action="store_true", help="Force the mock engine for route/CI validation"
    )
    parser.add_argument("--output", type=Path, help="Benchmark JSON store path")
    args = parser.parse_args(argv)

    if args.max_tokens < 1:
        parser.error("--max-tokens must be at least 1")
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    try:
        return asyncio.run(_main_async(args))
    except device_check.DeviceValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
