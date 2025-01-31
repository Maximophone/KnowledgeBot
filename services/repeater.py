import asyncio
from config import CONFIG
from typing import Callable
from config.logging_config import setup_logger

logger = setup_logger(__name__)

REPEATERS = []

class Repeater:
    """Runs tasks repeatedly at some time interval"""
    def __init__(self, config_name: str):
        self.config_name = config_name
        self.tasks = []
        self.task_names = []
        self.logger = setup_logger(f"{__name__}.{config_name}")

    async def start(self):
        self.logger.info("Repeater starting. Interval: %s", CONFIG.get(self.config_name))
        while True:
            for i, task in enumerate(self.tasks):
                self.logger.debug("Running task: %s", self.task_names[i])
                await task()
                self.logger.debug("Task finished: %s", self.task_names[i])
                await asyncio.sleep(0.05)
            
            self.logger.debug("Sleeping for %s seconds", CONFIG.get(self.config_name))
            await asyncio.sleep(CONFIG.get(self.config_name))
            self.logger.debug("Woke up")

    def register(self, func: Callable[[], None], name: str = None):
        self.logger.debug("Registering task: %s", name or func.__name__)
        self.tasks.append(func)
        self.task_names.append(name or func.__name__)
        return func

async def start_repeaters():
    logger.info("Starting all repeaters")
    await asyncio.gather(*[repeater.start() for repeater in REPEATERS])

slow_repeater = Repeater("slow_repeat_interval")
REPEATERS.append(slow_repeater)