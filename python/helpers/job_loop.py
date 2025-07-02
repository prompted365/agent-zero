import asyncio
import time
from typing import Dict

import aiocron
import pytz

from python.helpers.task_scheduler import TaskScheduler, ScheduledTask
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from python.helpers import runtime
from python.helpers.event_bus import AsyncEventBus
from python.helpers.localization import Localization


keep_running = True
pause_time = 0
cron_jobs: Dict[str, aiocron.Cron] = {}


async def schedule_jobs() -> None:
    scheduler = TaskScheduler.get()
    await scheduler.reload()
    tasks = scheduler.get_tasks()

    # Remove jobs for deleted tasks
    for uuid in list(cron_jobs.keys()):
        if not any(t.uuid == uuid for t in tasks if isinstance(t, ScheduledTask)):
            cron_jobs[uuid].stop()
            del cron_jobs[uuid]

    for task in tasks:
        if isinstance(task, ScheduledTask):
            cron_expr = task.schedule.to_crontab()
            tz = pytz.timezone(task.schedule.timezone or Localization.get().get_timezone())
            job = cron_jobs.get(task.uuid)
            if job and job.spec == cron_expr and job.tz == tz:
                continue
            if job:
                job.stop()
            cron_jobs[task.uuid] = aiocron.crontab(
                cron_expr,
                func=lambda uuid=task.uuid: asyncio.create_task(run_scheduled(uuid)),
                start=True,
                tz=tz,
            )


async def run_scheduled(task_uuid: str) -> None:
    if keep_running:
        try:
            scheduler = TaskScheduler.get()
            await scheduler.run_task_by_uuid(task_uuid)
        except Exception as e:
            PrintStyle().error(errors.format_error(e))


async def run_loop():
    global pause_time, keep_running

    scheduler = TaskScheduler.get()
    bus = AsyncEventBus.get()

    async def handle_event(*args, **kwargs):
        if runtime.is_development():
            try:
                await runtime.call_development_function(pause_loop)
            except Exception as e:
                PrintStyle().error(
                    "Failed to pause job loop by development instance: "
                    + errors.error_text(e)
                )
        if not keep_running and (time.time() - pause_time) > 120:
            resume_loop()
        if keep_running:
            try:
                await scheduler.tick()
            except Exception as e:
                PrintStyle().error(errors.format_error(e))
        await schedule_jobs()

    bus.on(
        "task.finished",
        lambda *a, **k: asyncio.create_task(handle_event(*a, **k)),
    )

    await schedule_jobs()
    await handle_event()
    await asyncio.Event().wait()


async def scheduler_tick():
    # Get the task scheduler instance and print detailed debug info
    scheduler = TaskScheduler.get()
    # Run the scheduler tick
    await scheduler.tick()


def pause_loop():
    global keep_running, pause_time
    keep_running = False
    pause_time = time.time()


def resume_loop():
    global keep_running, pause_time
    keep_running = True
    pause_time = 0
