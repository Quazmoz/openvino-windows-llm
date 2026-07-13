"""Benchmark OpenVINO GenAI device targets on local hardware.

Examples:
    python scripts/benchmark_devices.py tinyllama-1.1b-chat-fp16
    python scripts/benchmark_devices.py models/openvino/tinyllama-1.1b-chat-fp16 --experimental
    python scripts/benchmark_devices.py tinyllama-1.1b-chat-fp16 --devices "CPU;AUTO:NPU,GPU,CPU"
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import model_registry  # noqa: E402
from app.config import BASE_DIR  # noqa: E402
from runtime import device_check  # noqa: E402
from runtime.openvino_engine import build_plugin_config  # noqa: E402

DEFAULT_DEVICES = [
    "CPU",
    "GPU",
    "NPU",
    "AUTO:NPU,GPU,CPU",
    "AUTO:GPU,NPU,CPU",
]
EXPERIMENTAL_DEVICES = [
    "MULTI:NPU,GPU,CPU",
    "HETERO:NPU,GPU,CPU",
]
DEFAULT_PROMPT = (
    "You are running a local OpenVINO benchmark. In three short bullet points, "
    "summarize why measuring real hardware matters."
)


@dataclass
class BenchmarkResult:
    device: str
    success: bool
    load_time_s: float | None = None
    ttft_s: float | None = None
    latency_s: float | None = None
    output_tokens: int | None = None
    tokens_per_s: float | None = None
    runs: int = 0
    error: str | None = None


@dataclass
class GenerationRun:
    ttft_s: float | None
    latency_s: float
    output_tokens: int


def _result_text(result: Any) -> str:
    try:
        texts = getattr(result, "texts", None)
        if texts:
            return str(texts[0])
    except Exception:
        pass
    return str(result)


def _count_tokens(pipe: Any, text: str) -> int:
    try:
        tokenizer = pipe.get_tokenizer()
        ids = tokenizer.encode(text).input_ids
        try:
            return int(ids.get_shape()[-1])
        except Exception:
            return int(ids.shape[-1])
    except Exception:
        return max(1, len(text) // 4)


def _generation_config(ov_genai: Any, max_new_tokens: int) -> Any:
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = int(max_new_tokens)
    with_suppress = getattr(cfg, "do_sample", None)
    if with_suppress is not None:
        cfg.do_sample = False
    return cfg


def _generate_once(pipe: Any, ov_genai: Any, prompt: str, max_new_tokens: int) -> GenerationRun:
    cfg = _generation_config(ov_genai, max_new_tokens)
    first_token_at: float | None = None
    pieces: list[str] = []
    start = time.perf_counter()

    def streamer(piece: str) -> bool:
        nonlocal first_token_at
        if first_token_at is None:
            first_token_at = time.perf_counter()
        pieces.append(str(piece))
        return False

    try:
        pipe.generate(prompt, cfg, streamer)
        text = "".join(pieces)
    except TypeError:
        first_token_at = None
        result = pipe.generate(prompt, cfg)
        text = _result_text(result)

    latency = time.perf_counter() - start
    ttft = None if first_token_at is None else first_token_at - start
    return GenerationRun(ttft_s=ttft, latency_s=latency, output_tokens=_count_tokens(pipe, text))


def _resolve_model_path(model: str, models_file: Path) -> Path:
    candidate = Path(model)
    if candidate.exists() or candidate.is_absolute() or any(sep in model for sep in ("/", "\\")):
        return candidate if candidate.is_absolute() else (Path.cwd() / candidate).resolve()

    catalog = model_registry.load_catalog(models_file)
    cfg = catalog.get(model)
    if cfg:
        return cfg.abs_path(BASE_DIR)
    raise SystemExit(f"Unknown model id or path: {model}")


def _split_device_targets(raw: str) -> list[str]:
    """Split targets while preserving priority commas inside META:GPU,CPU values.

    Delegates to :func:`runtime.benchmark_runner.split_device_targets`,
    converting DeviceValidationError to SystemExit for CLI use.
    """
    from runtime.benchmark_runner import split_device_targets

    try:
        return split_device_targets(raw)
    except device_check.DeviceValidationError as exc:
        raise SystemExit(str(exc)) from exc


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def _format_rate(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _print_table(results: list[BenchmarkResult]) -> None:
    rows = [
        [
            result.device,
            "ok" if result.success else "fail",
            _format_seconds(result.load_time_s),
            _format_seconds(result.ttft_s),
            _format_seconds(result.latency_s),
            str(result.output_tokens) if result.output_tokens is not None else "-",
            _format_rate(result.tokens_per_s),
            result.error or "",
        ]
        for result in results
    ]
    headers = ["device", "status", "load_s", "ttft_s", "latency_s", "tokens", "tok/s", "error"]
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], min(len(cell), 72))

    def line(values: list[str]) -> str:
        clipped = [value if len(value) <= 72 else value[:69] + "..." for value in values]
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(clipped))

    print(line(headers))
    print(line(["-" * width for width in widths]))
    for row in rows:
        print(line(row))


def _benchmark_device(
    *,
    ov_genai: Any,
    model_path: Path,
    device: str,
    prompt: str,
    runs: int,
    max_new_tokens: int,
    max_prompt_len: int | None,
    cache_dir: Path | None,
) -> BenchmarkResult:
    try:
        config = build_plugin_config(device, max_prompt_len, cache_dir)
        load_start = time.perf_counter()
        if config:
            pipe = ov_genai.LLMPipeline(str(model_path), device, **config)
        else:
            pipe = ov_genai.LLMPipeline(str(model_path), device)
        load_time = time.perf_counter() - load_start

        generated = [_generate_once(pipe, ov_genai, prompt, max_new_tokens) for _ in range(runs)]
        latencies = [run.latency_s for run in generated]
        ttfts = [run.ttft_s for run in generated if run.ttft_s is not None]
        output_tokens = [run.output_tokens for run in generated]
        total_tokens = sum(output_tokens)
        total_latency = sum(latencies)
        pipe = None
        return BenchmarkResult(
            device=device,
            success=True,
            load_time_s=load_time,
            ttft_s=statistics.mean(ttfts) if ttfts else None,
            latency_s=statistics.mean(latencies),
            output_tokens=round(statistics.mean(output_tokens)),
            tokens_per_s=(total_tokens / total_latency) if total_latency > 0 else None,
            runs=runs,
        )
    except Exception as exc:  # noqa: BLE001 - a benchmark should continue across device failures
        return BenchmarkResult(device=device, success=False, runs=0, error=str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark OpenVINO GenAI device targets.")
    parser.add_argument(
        "model", help="Catalog model id from models.json or path to an OpenVINO model directory"
    )
    parser.add_argument(
        "--devices",
        help=(
            "Device targets. Comma-separated simple targets are accepted; use semicolons "
            "when listing composite targets, e.g. CPU;AUTO:NPU,GPU,CPU."
        ),
    )
    parser.add_argument("--experimental", action="store_true", help="Include MULTI/HETERO targets")
    parser.add_argument(
        "--runs", type=int, default=3, help="Generation runs per device (default 3)"
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=64, help="Generated token limit per run"
    )
    parser.add_argument("--max-prompt-len", type=int, default=1024, help="Exact-NPU MAX_PROMPT_LEN")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Fixed prompt used for every run")
    parser.add_argument(
        "--models-file", type=Path, default=BASE_DIR / "models.json", help="Catalog JSON path"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=BASE_DIR / "models" / "cache", help="OpenVINO cache dir"
    )
    parser.add_argument("--json", type=Path, help="Optional path to write JSON results")
    args = parser.parse_args(argv)

    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be at least 1")

    model_path = _resolve_model_path(args.model, args.models_file)
    if args.devices:
        devices = _split_device_targets(args.devices)
    else:
        devices = list(DEFAULT_DEVICES)
        if args.experimental:
            devices.extend(EXPERIMENTAL_DEVICES)

    try:
        import openvino_genai as ov_genai
    except Exception as exc:  # noqa: BLE001 - keep this script importable in CI/dev
        results = [
            BenchmarkResult(
                device=device, success=False, error=f"openvino_genai import failed: {exc}"
            )
            for device in devices
        ]
        _print_table(results)
        if args.json:
            args.json.write_text(
                json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8"
            )
        return 0

    print(f"Model: {model_path}")
    print(f"Prompt runs per device: {args.runs}")
    print()

    results = [
        _benchmark_device(
            ov_genai=ov_genai,
            model_path=model_path,
            device=device,
            prompt=args.prompt,
            runs=args.runs,
            max_new_tokens=args.max_new_tokens,
            max_prompt_len=args.max_prompt_len,
            cache_dir=args.cache_dir,
        )
        for device in devices
    ]
    _print_table(results)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8"
        )
        print(f"\nWrote JSON results to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
