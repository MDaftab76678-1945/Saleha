import pytest

from saleha.core.hardware_profiler import HardwareProfiler, HardwareSnapshot


@pytest.fixture
def hardware_profiler():
    return HardwareProfiler()


def test_snapshot(hardware_profiler):
    snapshot = hardware_profiler.snapshot()
    assert isinstance(snapshot, HardwareSnapshot)
    # Add assertions to check the properties of the snapshot


def test_record_window(hardware_profiler):
    snapshot1 = hardware_profiler.record_window(seconds=3.0, interval=0.75)
    snapshot2 = hardware_profiler.record_window(seconds=3.0, interval=0.75)
    assert snapshot1 != snapshot2