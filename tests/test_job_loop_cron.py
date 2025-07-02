import asyncio
import time
import pytest

import sys
import types

from python.helpers.task_scheduler import TaskScheduler, ScheduledTask, TaskSchedule

dummy_pyee = types.ModuleType('pyee')
class _DummyEmitter:
    def __init__(self, *a, **k):
        pass
sys.modules.setdefault('pyee', dummy_pyee)
dummy_pyee.AsyncIOEventEmitter = _DummyEmitter

dummy_event_bus = types.ModuleType('python.helpers.event_bus')
class _DummyEventBus:
    @classmethod
    def get(cls):
        return cls()
    def on(self, *a, **k):
        pass
    def emit(self, *a, **k):
        pass
dummy_event_bus.AsyncEventBus = _DummyEventBus
sys.modules['python.helpers.event_bus'] = dummy_event_bus

from python.helpers.job_loop import cron_jobs, schedule_jobs, resume_loop

def test_no_duplicate_runs_for_subminute(monkeypatch, tmp_path):
    async def _run():
        monkeypatch.setattr('python.helpers.task_scheduler.SCHEDULER_FOLDER', str(tmp_path))
        scheduler = TaskScheduler.get()
        await scheduler._tasks.save()

        schedule = TaskSchedule(second='*/1', minute='*', hour='*', day='*', month='*', weekday='*')
        task = ScheduledTask.create(name='t', system_prompt='', prompt='', schedule=schedule)
        await scheduler.add_task(task)

        calls = []

        async def fake_run(uuid):
            calls.append(time.time())

        monkeypatch.setattr(TaskScheduler, 'run_task_by_uuid', lambda self, uuid: fake_run(uuid))

        resume_loop()
        await schedule_jobs()

        start = time.time()
        for _ in range(4):
            await asyncio.sleep(0.5)
            await schedule_jobs()
        elapsed = time.time() - start

        for job in cron_jobs.values():
            job.stop()

        assert len(calls) <= int(elapsed) + 1

    asyncio.run(_run())
