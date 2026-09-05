import pytest

from saleha.core.hardware_profiler import HardwareProfiler, HardwareSnapshot


@pytest.fixture
def hardware_profiler():
    return HardwareProfiler()


def test_snapshot(hardware_profiler):
    snapshot = hardware_profiler.snapshot()
    assert isinstance(snapshot, HardwareSnapshot)
    assert snapshot.ts > 0
    assert 0.0 <= snapshot.cpu_percent <= 100.0
    assert snapshot.mem_total_mb > 0


def test_record_window(hardware_profiler):
    # Short window: the original 3.0s x2 calls added 6s of real sleep to the
    # suite for no assertion benefit beyond identity, which this keeps.
    snapshot1 = hardware_profiler.record_window(seconds=0.2, interval=0.1)
    snapshot2 = hardware_profiler.record_window(seconds=0.2, interval=0.1)
    assert isinstance(snapshot1, HardwareSnapshot)
    assert isinstance(snapshot2, HardwareSnapshot)
    assert snapshot2.ts >= snapshot1.ts
