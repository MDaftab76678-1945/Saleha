#!/usr/bin/env python3
"""Saleha Autonomous Orchestrator Kernel Entrypoint.

Direct alias and orchestrator entrypoint corresponding to the master architecture
diagram for autonomous closed-loop execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add current scripts directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from autonomous_kernel import main

if __name__ == "__main__":
    sys.exit(main())
