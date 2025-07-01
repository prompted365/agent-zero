import asyncio
import time
from python.helpers.task_scheduler import TaskScheduler
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from python.helpers import runtime
from python.helpers.event_bus import AsyncEventBus


SLEEP_TIME = 60

keep_running = True
pause_time = 0


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
        if not keep_running and (time.time() - pause_time) > (SLEEP_TIME * 2):
            resume_loop()
        if keep_running:
            try:
                await scheduler.tick()
            except Exception as e:
                PrintStyle().error(errors.format_error(e))

    bus.on(
        "task.finished",
        lambda *a, **k: asyncio.create_task(handle_event(*a, **k)),
    )

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
