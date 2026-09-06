"""Test suite for saleha.core.agent_worker_pool."""

import time

from saleha.core.agent_worker_pool import AgentWorkerPool, WorkerTaskResult


class TestAgentWorkerPool:
    """Thread-pool based task executor with timeout enforcement."""

    def test_execute_task_success(self):
        pool = AgentWorkerPool(max_workers=2)
        result = pool.execute_task("t1", lambda x: x + 1, 41, timeout_sec=2.0)

        assert isinstance(result, WorkerTaskResult)
        assert result.success is True
        assert result.result == 42
        assert result.error_message is None
        pool.shutdown()

    def test_execute_task_with_kwargs(self):
        pool = AgentWorkerPool(max_workers=2)

        def add(a, b=0):
            return a + b

        result = pool.execute_task("t2", add, 10, b=5, timeout_sec=2.0)

        assert result.success is True
        assert result.result == 15
        pool.shutdown()

    def test_execute_task_timeout(self):
        pool = AgentWorkerPool(max_workers=2)
        result = pool.execute_task("t3", time.sleep, 2, timeout_sec=0.1)

        assert result.success is False
        assert result.error_message is not None
        pool.shutdown()

    def test_execute_task_exception(self):
        pool = AgentWorkerPool(max_workers=2)

        def raises():
            raise ValueError("boom")

        result = pool.execute_task("t4", raises, timeout_sec=2.0)

        assert result.success is False
        assert "boom" in result.error_message
        pool.shutdown()

    def test_multiple_concurrent_tasks(self):
        pool = AgentWorkerPool(max_workers=4)

        results = [
            pool.execute_task(f"t{i}", lambda x: x * 2, i, timeout_sec=2.0)
            for i in range(5)
        ]

        assert all(r.success for r in results)
        assert [r.result for r in results] == [0, 2, 4, 6, 8]
        pool.shutdown()

    def test_execution_time_recorded(self):
        pool = AgentWorkerPool(max_workers=1)
        result = pool.execute_task("t5", lambda: "done", timeout_sec=2.0)

        assert result.success is True
        assert result.execution_time_ms >= 0
        pool.shutdown()

    def test_shutdown(self):
        pool = AgentWorkerPool(max_workers=1)
        pool.execute_task("t6", lambda: 1, timeout_sec=2.0)
        pool.shutdown(wait=True)
