from __future__ import annotations

import asyncio

from app.hardware_advisor.auto_benchmark import AutoBenchmarkRunnerMixin


class Runner(AutoBenchmarkRunnerMixin):
    pass


def test_shutdown_drains_tasks_spawned_by_cancellation_cleanup():
    async def exercise() -> None:
        runner = Runner()
        runner._tasks = set()
        started = asyncio.Event()
        spawned: list[asyncio.Task] = []

        async def parent() -> None:
            try:
                started.set()
                await asyncio.Future()
            finally:
                child = asyncio.create_task(asyncio.sleep(60), name="late-advisor-task")
                spawned.append(child)
                runner._tasks.add(child)

        parent_task = asyncio.create_task(parent(), name="advisor-finalizer")
        runner._tasks.add(parent_task)
        await started.wait()

        await runner.shutdown()

        assert not runner._tasks
        assert parent_task.done()
        assert spawned
        assert all(task.done() for task in spawned)

    asyncio.run(exercise())
