"""Concurrency checker: each rule fires on the bug and stays quiet on the fix."""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import List

from saleha.core.verification.concurrency_checker import check_source
from saleha.sandbox.local_llm_driver import LocalLLMDriver


def rules(src: str) -> List[str]:
    return [f.rule for f in check_source(src)]


RACY_COUNTER = '''
import threading
hits = 0
def work():
    global hits
    hits += 1
def report():
    return hits
threading.Thread(target=work).start()
'''

LOCKED_COUNTER = '''
import threading
hits = 0
lock = threading.Lock()
def work():
    global hits
    with lock:
        hits += 1
def report():
    return hits
threading.Thread(target=work).start()
'''


class ConcurrencyRuleTests(unittest.TestCase):
    def test_c001_unlocked_shared_write(self) -> None:
        self.assertIn("C001", rules(RACY_COUNTER))
        self.assertNotIn("C001", rules(LOCKED_COUNTER))

    def test_c001_ignores_state_only_its_own_thread_touches(self) -> None:
        private = '''
import threading
class Watcher:
    def __init__(self):
        self._seen = {}
    def _loop(self):
        self._seen["a"] = 1
    def start(self):
        threading.Thread(target=self._loop).start()
'''
        self.assertNotIn("C001", rules(private))

    def test_c002_check_then_act(self) -> None:
        src = '''
from concurrent.futures import ThreadPoolExecutor
cache = {}
def fill(k):
    if k not in cache:
        cache[k] = k * 2
def get(k):
    return cache[k]
ThreadPoolExecutor().submit(fill, 1)
'''
        self.assertIn("C002", rules(src))

    def test_c003_acquire_without_finally_release(self) -> None:
        bad = "def f(lock):\n    lock.acquire()\n    do()\n    lock.release()\n"
        good = "def f(lock):\n    lock.acquire()\n    try:\n        do()\n    finally:\n        lock.release()\n"
        self.assertIn("C003", rules(bad))
        self.assertNotIn("C003", rules(good))

    def test_c004_lock_order_inversion(self) -> None:
        src = '''
def a():
    with lock_x:
        with lock_y:
            pass
def b():
    with lock_y:
        with lock_x:
            pass
'''
        self.assertIn("C004", rules(src))
        same_order = src.replace("with lock_y:\n        with lock_x:", "with lock_x:\n        with lock_y:")
        self.assertNotIn("C004", rules(same_order))

    def test_c005_blocking_call_in_async(self) -> None:
        self.assertIn("C005", rules("import time\nasync def f():\n    time.sleep(1)\n"))
        offloaded = ("import asyncio, time\nasync def f():\n    def work():\n        time.sleep(1)\n"
                     "    await asyncio.to_thread(work)\n")
        self.assertNotIn("C005", rules(offloaded))

    def test_c006_dropped_task(self) -> None:
        self.assertIn("C006", rules("import asyncio\nasync def f():\n    asyncio.create_task(g())\n"))
        self.assertNotIn("C006", rules("import asyncio\nasync def f():\n    t = asyncio.create_task(g())\n    await t\n"))


class OfflineDriverTests(unittest.TestCase):
    """The driver used to answer an unreachable model with canned code whose
    own self-test printed SELF_TEST_PASSED."""

    def test_unreachable_model_is_an_error_not_code(self) -> None:
        driver = LocalLLMDriver(ollama_url="http://127.0.0.1:9", vllm_url="http://127.0.0.1:9/v1")
        res = asyncio.run(driver.generate_structured("Agent Specification please"))
        self.assertIn("error", res)
        self.assertNotIn("code", res)
        self.assertNotIn("SELF_TEST_PASSED", json.dumps(res))

    def test_unreachable_embedding_is_empty_not_fake(self) -> None:
        driver = LocalLLMDriver(ollama_url="http://127.0.0.1:9")
        self.assertEqual(asyncio.run(driver.get_embedding("hello")), [])


if __name__ == "__main__":
    unittest.main()
