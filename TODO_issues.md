# Outstanding TODOs

This file tracks TODO comments that remain in the codebase for future implementation.

- **python/helpers/mcp_handler.py** lines 763-765: prompts should be external files with placeholders.
- **python/helpers/settings.py** lines 1033, 1091, 1096, 1106: current synchronous operations could be moved to background tasks; token generation is messy.
- **python/helpers/vector_db.py** line 5 and **python/helpers/memory.py** line 9: remove faiss patch once official support for Python 3.12 on ARM becomes available.
- **docker/run/fs/etc/searxng/settings.yml** lines 7 and 70: enable `radio_browser` when it works again.
- **agent.py** line 600: add parameterization for message range, topic, and history.
- **webui/js/speech_browser.js** line 221 and **speech.js** line 251: find a cleaner way to ignore the agent's voice.

