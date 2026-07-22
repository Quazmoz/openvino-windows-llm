"""Short post-load benchmark execution for the hardware advisor."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app import chat_format
from runtime.openvino_engine import GenParams

from .common import AUTOMATIC_PROMPT, utc_now


class AutoBenchmarkRunnerMixin:
    def schedule_auto_benchmark(
        self,
        manager: Any,
        model_id: str,
        *,
        load_time_ms: float | None = None,
    ) -> None:
        if self.force_mock or model_id not in manager.engines:
            return
        cfg = manager.catalog.get(model_id)
        if cfg is None or "embedding" in str(getattr(cfg, "backend", "")).lower():
            return
        device = manager.devices.get(model_id) or getattr(manager.engines[model_id], "device", "CPU")
        if self._recent_auto_benchmark_exists(model_id, device):
            return
        task = asyncio.create_task(
            self._run_auto_benchmark(manager, model_id, device, load_time_ms=load_time_ms),
            name=f"advisor-benchmark-{model_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_auto_benchmark(
        self,
        manager: Any,
        model_id: str,
        device: str,
        *,
        load_time_ms: float | None,
    ) -> None:
        await asyncio.sleep(1.0)
        lock = manager.get_lock(model_id)
        for _ in range(60):
            if not lock.locked():
                break
            await asyncio.sleep(0.5)
        engine = manager.engines.get(model_id)
        cfg = manager.catalog.get(model_id)
        if engine is None or cfg is None:
            return
        try:
            prompt, prompt_tokens = await asyncio.to_thread(
                chat_format.build_prompt_within_budget,
                [{"role": "user", "content": AUTOMATIC_PROMPT}],
                engine.apply_chat_template,
                engine.count_tokens,
                cfg.max_prompt_len,
            )
            params = GenParams(
                max_new_tokens=min(24, max(cfg.max_context_len - prompt_tokens - 8, 1)),
                temperature=0.0,
                top_p=1.0,
                do_sample=False,
            )
            started = time.perf_counter()
            first_token_at: float | None = None
            chunks: list[str] = []
            stream = manager.stream(engine, prompt, params)
            try:
                async for piece in stream:
                    if first_token_at is None and piece:
                        first_token_at = time.perf_counter()
                    chunks.append(piece)
            finally:
                await stream.aclose()
            latency_s = max(time.perf_counter() - started, 0.000001)
            text = "".join(chunks)
            completion_tokens = await asyncio.to_thread(engine.count_tokens, text)
            tps = completion_tokens / latency_s
            run_id = f"auto-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
            result = {
                "run_id": run_id,
                "model_id": model_id,
                "requested_device": device,
                "actual_device": getattr(engine, "actual_device", None) or getattr(engine, "device", device),
                "load_time_ms": round(load_time_ms, 3) if load_time_ms is not None else None,
                "time_to_first_token_ms": (
                    round((first_token_at - started) * 1000, 3) if first_token_at is not None else None
                ),
                "total_latency_ms": round(latency_s * 1000, 3),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "tokens_sec": round(tps, 3),
                "success": True,
                "error": None,
                "timestamp": utc_now(),
                "runs": 1,
                "score": None,
            }
            run = {
                "run_id": run_id,
                "created_at": utc_now(),
                "finished_at": utc_now(),
                "prompt": AUTOMATIC_PROMPT,
                "max_tokens": 24,
                "runs_per_combo": 1,
                "mock": False,
                "automatic": True,
                "hardware_fingerprint": self.hardware_snapshot().get("fingerprint"),
                "results": [result],
                "recommendation": {
                    "model_id": model_id,
                    "requested_device": device,
                    "actual_device": result["actual_device"],
                    "score": None,
                    "summary": f"Automatic short benchmark completed for {model_id} on {device}.",
                    "rationale": [
                        f"{tps:.2f} tokens/sec",
                        f"{result['time_to_first_token_ms']:.1f} ms first-token latency"
                        if result["time_to_first_token_ms"] is not None
                        else "First-token latency was unavailable.",
                    ],
                    "caveat": "This short benchmark is local evidence, not a general performance guarantee.",
                },
                "caveat": "Automatic short benchmark; run the full benchmark suite for comparative evidence.",
            }
            await asyncio.to_thread(self._append_run, run)
            manager.emit_event(
                "info",
                f"Hardware advisor benchmarked {cfg.name} on {device} ({tps:.1f} t/s)",
            )
            # Refresh estimates so measured load and throughput evidence appears immediately.
            self._snapshot_at = 0.0
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - background evidence must never break model loading
            manager.emit_event("warning", f"Automatic advisor benchmark skipped for {cfg.name}: {exc}")

    async def shutdown(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
