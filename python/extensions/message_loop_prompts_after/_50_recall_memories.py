import asyncio
import hashlib
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from agent import LoopData
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD
from python.helpers import dirty_json, errors, settings, log


DATA_NAME_TASK = "_recall_memories_task"
DATA_NAME_ITER = "_recall_memories_iter"
SEARCH_TIMEOUT = 300  # 5 minutes — reasoning models need breathing room

# Module-level query cache: avoids redundant FAISS searches for identical queries.
# Keyed by (query_hash, threshold, mem_limit, sol_limit). Value: (memories_txt, solutions_txt).
# Survives across iterations within the same monologue (module-level var).
# Max 8 entries to bound memory. Cleared on process restart.
_query_cache: dict[str, tuple[str, str]] = {}
_QUERY_CACHE_MAX = 8


def _cache_key(query: str, threshold: float, mem_limit: int, sol_limit: int) -> str:
    h = hashlib.md5(query.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{h}:{threshold}:{mem_limit}:{sol_limit}"


class RecallMemories(Extension):

    # INTERVAL = 3
    # HISTORY = 10000
    # MEMORIES_MAX_SEARCH = 12
    # SOLUTIONS_MAX_SEARCH = 8
    # MEMORIES_MAX_RESULT = 5
    # SOLUTIONS_MAX_RESULT = 3
    # THRESHOLD = DEFAULT_MEMORY_THRESHOLD

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):

        set = settings.get_settings()

        # turned off in settings?
        if not set["memory_recall_enabled"]:
            return

        # every X iterations (or the first one) recall memories
        if loop_data.iteration % set["memory_recall_interval"] == 0:

            # show util message right away
            log_item = self.agent.context.log.log(
                type="util",
                heading="Searching memories...",
            )

            task = asyncio.create_task(
                asyncio.wait_for(
                    self.search_memories(loop_data=loop_data, log_item=log_item, **kwargs),
                    timeout=SEARCH_TIMEOUT,
                )
            )
        else:
            task = None

        # set to agent to be able to wait for it
        self.agent.set_data(DATA_NAME_TASK, task)
        self.agent.set_data(DATA_NAME_ITER, loop_data.iteration)

    async def search_memories(self, log_item: log.LogItem, loop_data: LoopData, **kwargs):

        # cleanup
        extras = loop_data.extras_persistent
        if "memories" in extras:
            del extras["memories"]
        if "solutions" in extras:
            del extras["solutions"]


        set = settings.get_settings()
        # try:

        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.memories_query.sys.md")

        # # log query streamed by LLM
        # async def log_callback(content):
        #     log_item.stream(query=content)

        # call util llm to summarize conversation
        user_instruction = (
            loop_data.user_message.output_text() if loop_data.user_message else "None"
        )
        history = self.agent.history.output_text()[-set["memory_recall_history_len"]:]
        message = self.agent.read_prompt(
            "memory.memories_query.msg.md", history=history, message=user_instruction
        )

        # if query preparation by AI is enabled
        if set["memory_recall_query_prep"]:
            try:
                # call util llm to generate search query from the conversation
                query = await self.agent.call_utility_model(
                    system=system,
                    message=message,
                    # callback=log_callback,
                )
                query = query.strip()
                log_item.update(query=query) # no need for streaming here
            except Exception as e:
                err = errors.format_error(e)
                self.agent.context.log.log(
                    type="warning", heading="Recall memories extension error:", content=err
                )
                query = ""

            # no query, no search
            if not query:
                log_item.update(
                    heading="Failed to generate memory query",
                )
                return
        
        # otherwise use the message and history as query
        else:
            query = user_instruction + "\n\n" + history

        # if there is no query (or just dash by the LLM), do not continue
        if not query or len(query) <= 3:
            log_item.update(
                query="No relevant memory query generated, skipping search",
            )
            return

        # Check query cache before hitting FAISS
        global _query_cache
        ck = _cache_key(
            query,
            set["memory_recall_similarity_threshold"],
            set["memory_recall_memories_max_search"],
            set["memory_recall_solutions_max_search"],
        )
        if ck in _query_cache:
            cached_mem, cached_sol = _query_cache[ck]
            log_item.update(heading="Recalled from query cache (FAISS skipped)")
            if cached_mem:
                extras["memories"] = cached_mem
            if cached_sol:
                extras["solutions"] = cached_sol
            return

        # get memory database
        db = await Memory.get(self.agent)

        # search for general memories and fragments
        try:
            memories = await db.search_similarity_threshold(
                query=query,
                limit=set["memory_recall_memories_max_search"],
                threshold=set["memory_recall_similarity_threshold"],
                filter=f"area == '{Memory.Area.MAIN.value}' or area == '{Memory.Area.FRAGMENTS.value}'",  # exclude solutions
            )
        except ValueError as e:
            if "Could not find document for id" in str(e):
                log_item.update(heading=f"Memory recall degraded: FAISS index desync ({e})")
                memories = []
            else:
                raise

        # search for solutions
        try:
            solutions = await db.search_similarity_threshold(
                query=query,
                limit=set["memory_recall_solutions_max_search"],
                threshold=set["memory_recall_similarity_threshold"],
                filter=f"area == '{Memory.Area.SOLUTIONS.value}'",  # exclude solutions
            )
        except ValueError as e:
            if "Could not find document for id" in str(e):
                log_item.update(heading=f"Solution recall degraded: FAISS index desync ({e})")
                solutions = []
            else:
                raise

        # Stash raw FAISS results for downstream dedup (_55 drift tracker).
        # Drift tracker fires after recall — can skip its own FAISS scan
        # when recall already searched MAIN+FRAGMENTS.
        self.agent.set_data("_recall_faiss_docs", [
            doc.page_content[:500] for doc in memories[:5]
        ])

        if not memories and not solutions:
            log_item.update(
                heading="No memories or solutions found",
            )
            return

        # if post filtering is enabled
        if set["memory_recall_post_filter"]:
            # assemble an enumerated dict of memories and solutions for AI validation
            mems_list = {i: memory.page_content for i, memory in enumerate(memories + solutions)}

            # call AI to validate the memories
            try:
                filter = await self.agent.call_utility_model(
                    system=self.agent.read_prompt("memory.memories_filter.sys.md"),
                    message=self.agent.read_prompt(
                        "memory.memories_filter.msg.md",
                        memories=mems_list,
                        history=history,
                        message=user_instruction,
                    ),
                )
                filter_inds = dirty_json.try_parse(filter)

                # filter memories and solutions based on filter_inds
                filtered_memories = []
                filtered_solutions = []
                mem_len = len(memories)

                # process each index in filter_inds
                # make sure filter_inds is a list and contains valid integers
                if isinstance(filter_inds, list):
                    for idx in filter_inds:
                        if isinstance(idx, int):
                            if idx < mem_len:
                                # this is a memory
                                filtered_memories.append(memories[idx])
                            else:
                                # this is a solution, adjust index
                                sol_idx = idx - mem_len
                                if sol_idx < len(solutions):
                                    filtered_solutions.append(solutions[sol_idx])

                # replace original lists with filtered ones
                memories = filtered_memories
                solutions = filtered_solutions

            except Exception as e:
                err = errors.format_error(e)
                self.agent.context.log.log(
                    type="warning", heading="Failed to filter relevant memories", content=err
                )
                filter_inds = []


        # limit the number of memories and solutions
        memories = memories[: set["memory_recall_memories_max_result"]]
        solutions = solutions[: set["memory_recall_solutions_max_result"]]

        # log the search result
        log_item.update(
            heading=f"{len(memories)} memories and {len(solutions)} relevant solutions found",
        )

        memories_txt = "\n\n".join([mem.page_content for mem in memories]) if memories else ""
        solutions_txt = "\n\n".join([sol.page_content for sol in solutions]) if solutions else ""

        # log the full results
        if memories_txt:
            log_item.update(memories=memories_txt)
        if solutions_txt:
            log_item.update(solutions=solutions_txt)

        # place to prompt
        mem_prompt = ""
        sol_prompt = ""
        if memories_txt:
            mem_prompt = self.agent.parse_prompt(
                "agent.system.memories.md", memories=memories_txt
            )
            extras["memories"] = mem_prompt
        if solutions_txt:
            sol_prompt = self.agent.parse_prompt(
                "agent.system.solutions.md", solutions=solutions_txt
            )
            extras["solutions"] = sol_prompt

        # Cache the formatted results for identical future queries
        if mem_prompt or sol_prompt:
            if len(_query_cache) >= _QUERY_CACHE_MAX:
                # Evict oldest entry (FIFO)
                _query_cache.pop(next(iter(_query_cache)))
            _query_cache[ck] = (mem_prompt, sol_prompt)
