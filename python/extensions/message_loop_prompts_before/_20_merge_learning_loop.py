from python.helpers.extension import Extension
from python.helpers.learning_loop import LearningLoop
from agent import LoopData

from python.extensions.monologue_start._70_init_learning_loop import DATA_NAME_LEARNING_LOOP


class MergeLearningLoop(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        loop: LearningLoop | None = self.agent.get_data(DATA_NAME_LEARNING_LOOP)
        if not loop:
            return
        retro = loop.summarize_retro()
        proj = loop.summarize_projected()
        if retro:
            loop_data.extras_persistent["log_learning_retro"] = self.agent.parse_prompt(
                "agent.system.log_learning.retro.md", logs=retro
            )
        if proj:
            loop_data.extras_persistent["log_learning_projected"] = self.agent.parse_prompt(
                "agent.system.log_learning.projected.md", logs=proj
            )
