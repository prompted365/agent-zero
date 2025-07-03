from python.helpers.extension import Extension
from python.helpers.learning_loop import LearningLoop
from agent import LoopData

DATA_NAME_LEARNING_LOOP = "learning_loop"


class InitLearningLoop(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent.get_data(DATA_NAME_LEARNING_LOOP):
            loop = LearningLoop()
            loop.start()
            self.agent.set_data(DATA_NAME_LEARNING_LOOP, loop)
