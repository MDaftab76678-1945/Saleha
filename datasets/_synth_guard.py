"""Shared re-run guard for dataset synthesizer scripts in this directory.

Several scripts here (synthesize_sovereign_ultra_dataset.py,
synthesize_tourist_gemini_dataset.py, synthesize_omni_leaderboard_data.py,
synthesize_hardcore_data.py, synthesize_asi_math_reasoning_data.py) had a
counter-based cloning bug: a tiny set of real, correct templates was
duplicated hundreds of times with only a "[Batch #N]"-style tag changed,
producing output files that claimed far more real diversity than existed.
The real output files were manually deduplicated on 2026-09-06 (see
datasets/_pre_cleanup_backup_20260906/ for the pre-cleanup originals) and
each script's docstring was updated to say "do not re-run" -- but nothing
in the code actually stopped a re-run from silently overwriting the
deduplicated file with the fabricated one again. This closes that gap.
"""

from __future__ import annotations

import os
import sys


def guard_output_path(output_path: str, script_name: str) -> None:
    """Refuses to overwrite an existing output file unless --force is passed.

    Call this before writing any dataset output file. Exits the process
    with a non-zero code and an explanation if the file exists and --force
    was not given on the command line.
    """
    if not os.path.exists(output_path):
        return
    if "--force" in sys.argv:
        print(
            f"[{script_name}] --force given: overwriting existing "
            f"{output_path}. If this file was hand-deduplicated, this will "
            f"destroy that work -- see datasets/_pre_cleanup_backup_20260906/ "
            f"for what the un-deduplicated version looked like last time."
        )
        return
    print(
        f"[{script_name}] Refusing to overwrite {output_path}: it already "
        f"exists. This script previously had a bug that cloned a handful of "
        f"real templates hundreds of times with only a counter changed; the "
        f"file at this path has since been manually deduplicated. Re-running "
        f"this script would silently replace that real data with fabricated "
        f"volume again. If you specifically want to regenerate it (e.g. "
        f"after adding genuinely new templates to this script), pass --force."
    )
    sys.exit(1)
