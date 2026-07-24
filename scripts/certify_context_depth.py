"""Run one deterministic, throughput-free model context-depth certification."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.config import Settings
from app.model_manager import ModelManager
from runtime.benchmark_runner import certify_context_depth


async def _run(args: argparse.Namespace) -> int:
    settings = Settings.from_env().replace(default_model=None, force_mock=None)
    manager = ModelManager(settings)
    cfg = manager.config_for(args.model)
    if cfg is None:
        raise ValueError(f"Unknown model '{args.model}'.")
    requested_context = args.context or cfg.max_prompt_len
    result = await certify_context_depth(
        manager,
        model_id=args.model,
        device=args.device,
        requested_context=requested_context,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument(
        "--context",
        type=int,
        default=0,
        help="Exact prompt-token depth; 0 uses the model's configured maximum prompt length.",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
