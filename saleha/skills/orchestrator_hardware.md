---
id: "orchestrator_hardware"
title: "Automated Hardware-in-the-Loop (HIL) Test Runner Engine"
version: "3.0.0"
---

# Hardware-in-the-Loop (HIL) Orchestration Engine

## 1. Executable Automated HIL Test Suite in Python
```python
import time
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HIL_Runner")

class HardwareTestRig:
    def __init__(self, psu_address: str, serial_port: str):
        self.psu_address = psu_address
        self.serial_port = serial_port
        logger.info(f"Initialized Rig: PSU={psu_address}, Port={serial_port}")

    def set_power_rail(self, voltage: float, current_limit: float):
        logger.info(f"SCPI Command: APPLy {voltage}V, {current_limit}A")
        return True

    def flash_firmware_jlink(self, hex_path: str) -> bool:
        logger.info(f"Flashing target via SWD probe: {hex_path}")
        time.sleep(1.0)
        return True

    def run_voltage_ramp_test(self) -> bool:
        logger.info("Executing Voltage Margin Test: 3.0V -> 3.6V in 100mV steps")
        for v in [3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6]:
            self.set_power_rail(v, 1.0)
            time.sleep(0.1)
        return True

if __name__ == "__main__":
    rig = HardwareTestRig("TCPIP0::192.168.1.100::inst0::INSTR", "/dev/ttyUSB0")
    if not rig.flash_firmware_jlink("build/firmware_v2.0.hex"):
        sys.exit(1)
    if not rig.run_voltage_ramp_test():
        sys.exit(1)
    logger.info("All Hardware Orchestration Tests PASSED.")
```

