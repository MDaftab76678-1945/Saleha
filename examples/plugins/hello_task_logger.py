"""
Saleha Example Plugin: Task Logger Hook

Ye dikhata hai ki Saleha plugin system kaise use hota hai -- kisi bhi
`on_*` event naam ka module-level function define karo, file ko
`~/.saleha/plugins/` (ya `.saleha/plugins/`) me daalo. Loader khud
discover karke register kar dega.

Available events:
  - on_task_start(goal=..., **kw)
  - on_code_generated(code=..., **kw)
  - on_test_complete(result=..., **kw)

Is plugin har task start ka timestamp ~/.saleha/plugin_task_log.jsonl me
append karta hai.
"""

import os
import time

PLUGIN_NAME = "task-logger"


def on_task_start(goal="", **kwargs):
    log_path = os.path.join(os.path.expanduser("~"), ".saleha", "plugin_task_log.jsonl")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f'{{"ts": {time.time():.3f}, "goal": {goal!r}}}\n')
        return f"logged: {goal[:60]}"
    except OSError:
        return None
