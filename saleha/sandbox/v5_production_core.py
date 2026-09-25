"""
v5 self-healing engine: generate -> AST audit -> jailed run -> retry.

What a "pass" here means, stated because it is easy to over-read: the model
writes both the code and the asserts that check it, so SELF_TESTS_PASSED is
"the model's own asserts did not fail inside the jail". Nothing independent
checks the result. Results carry `verified_by` saying exactly that.

Fixed in this module (pass 158):

- The SQLite solution cache keyed on `abs(hash(task_spec))`. `str` hashes are
  salted per process, so the "persistent memory" could never hit across runs.
  It keys on SHA-256 now.
- `failing_code` was saved as the code that had just passed (the same
  variable), so the cache never held the failure it claims to remember.
- `logging.basicConfig` ran at import, reconfiguring the root logger of any
  process that merely imported this module; it runs in `main()` only.
- Log lines carried emoji, which raise UnicodeEncodeError on a cp1252 console.
- Default paths were relative to the working directory, one of them outside
  it (`../01_agent_specs`); both live under ~/.saleha/v5 now. A domain name
  went into a filename unsanitised (`../` included).
- A model reply whose `code` was not a string crashed the audit.
"""

import asyncio
import hashlib
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from saleha.sandbox.ast_security_verifier import ASTContractAuditor

# These were flat imports (`from local_llm_driver import ...`), which only
# resolve when this directory is the working directory. Imported as part of
# the package -- which is how everything else in the repo reaches it -- they
# raised ModuleNotFoundError, so this module could not be imported at all.
from saleha.sandbox.local_llm_driver import LocalLLMDriver
from saleha.sandbox.sandbox_jail import HardenedSandbox, SandboxUnavailableError

logger = logging.getLogger("V5_ProductionEngine")

V5_HOME = Path.home() / ".saleha" / "v5"
VERIFIED_BY = "the model's own asserts (no independent test)"


def task_key(task_spec: str) -> str:
    """Stable across processes, unlike hash() on str."""
    return hashlib.sha256(task_spec.encode("utf-8")).hexdigest()


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unnamed"


class PersistentSwarmDB:
    def __init__(self, db_path: Union[str, Path, None] = None):
        path = Path(db_path) if db_path is not None else V5_HOME / "swarm_memory.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS error_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT UNIQUE,
                    failing_code TEXT,
                    resolved_code TEXT,
                    error_traceback TEXT,
                    timestamp REAL
                )
            """)

    def save_resolution(self, task_hash: str, bad_code: str, good_code: str, error_msg: str):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO error_memory VALUES (NULL, ?, ?, ?, ?, ?)",
                (task_hash, bad_code, good_code, error_msg, time.time())
            )

    def get_past_solution(self, task_hash: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT resolved_code FROM error_memory WHERE task_hash = ?", (task_hash,))
        row = cur.fetchone()
        return row[0] if row else None


class SwarmGenesisRegistry:
    def __init__(self, specs_dir: Union[str, Path, None] = None):
        self.specs_dir = Path(specs_dir) if specs_dir is not None else V5_HOME / "agent_specs"
        self.specs_dir.mkdir(parents=True, exist_ok=True)

    def spec_path(self, domain: str) -> Path:
        return self.specs_dir / f"agent_{_safe_slug(domain)}.md"

    def agent_exists(self, domain_key: str) -> bool:
        # Exact file, not a substring: "go" must not match agent_golang.md.
        return self.spec_path(domain_key).is_file()

    async def generate_agent_persona(self, domain: str, requirement: str, llm: LocalLLMDriver) -> str:
        logger.info(f"Capability gap: synthesizing persona for '{domain}'...")
        slug = _safe_slug(domain)
        prompt = f"""
Write an Agent Specification in Markdown format with YAML frontmatter.
Domain: {domain}
Core Goal: {requirement}

Required structure:
---
id: "agent_{slug}"
name: "{domain.title()} Specialist"
type: "agent_profile"
version: "5.0.0"
goals:
  - "{requirement}"
constraints:
  - "Defensive validation required"
  - "Zero uncontrolled exceptions"
---
# {domain.title()} Operational Guidelines
Explain responsibilities and validation checklists.
"""
        response = await llm.generate_structured(
            prompt=prompt,
            system_prompt="You are an AI System Architect. Output strict YAML + Markdown.",
            json_mode=False
        )

        # No model answer means no persona. Writing an empty spec and logging
        # "Persona registered" was a success report for work never done.
        if response.get("error") or not str(response.get("raw_text", "")).strip():
            raise RuntimeError(f"persona for '{domain}' not generated: "
                               f"{response.get('error') or 'model returned no text'}")
        filepath = self.spec_path(domain)
        filepath.write_text(str(response.get("raw_text", "")).strip() + "\n", encoding="utf-8")

        logger.info(f"Persona registered: {filepath}")
        return str(filepath)


class SelfHealingEngine:
    """
    Generate -> AST audit -> sandboxed execution -> retry loop.

    Every verification path here runs code through `HardenedSandbox`, which is
    POSIX-only. Refuse at construction rather than partway through a healing
    run: the alternative is discovering the platform limit after a model call,
    or -- worse -- someone removing the sandbox step to make it work on
    Windows and leaving the "verified in sandbox" log line in place.
    """

    def __init__(self):
        if not HardenedSandbox.is_available():
            raise SandboxUnavailableError(
                f"SelfHealingEngine verifies generated code inside the POSIX "
                f"jail, and {HardenedSandbox.unavailable_reason()}"
            )
        self.llm = LocalLLMDriver()
        self.sandbox = HardenedSandbox(max_mem_mb=128, max_cpu_sec=3)
        self.db = PersistentSwarmDB()
        self.registry = SwarmGenesisRegistry()

    async def execute_task_with_healing(self, task_spec: str, max_retries: int = 3) -> Dict[str, Any]:
        task_hash = task_key(task_spec)

        # 1. Check persistent memory cache (re-run in the jail, never trusted as-is)
        cached_fix = self.db.get_past_solution(task_hash)
        if cached_fix:
            logger.info("[cache hit] Found a previous solution in SQLite; re-running it in the jail...")
            res = self.sandbox.run_isolated(cached_fix)
            if res["passed"]:
                return {"status": "RESOLVED_FROM_MEMORY", "attempts": 0, "code": cached_fix,
                        "stdout": res["stdout"], "verified_by": VERIFIED_BY}

        previous_code = ""
        failing_code = ""
        last_error = ""

        for attempt in range(1, max_retries + 1):
            logger.info(f"[healing loop] Attempt {attempt}/{max_retries}...")

            system_prompt = (
                "You are an expert systems programmer. You generate clean, bug-free Python code. "
                "Respond ONLY with a JSON object having keys: 'code' (string containing full runnable python code) and 'explanation' (string)."
            )

            if attempt == 1:
                prompt = (
                    f"Write a self-testing Python script for this task:\n{task_spec}\n\n"
                    f"Requirements: Must include input type asserts, defensive invariant asserts, and self-test calls."
                )
            else:
                prompt = (
                    f"The previous attempt failed. Fix the code according to the traceback.\n\n"
                    f"Task: {task_spec}\n"
                    f"Failed Code:\n{previous_code}\n\n"
                    f"Error Output:\n{last_error}\n\n"
                    f"Return the corrected JSON payload."
                )

            structured_resp = await self.llm.generate_structured(prompt, system_prompt, json_mode=True)
            if structured_resp.get("error"):
                return {"status": "NOT_RUN", "attempts": attempt, "reason": structured_resp["error"]}
            code = structured_resp.get("code")
            if not isinstance(code, str) or not code.strip():
                last_error = f"model reply had no 'code' string (got {type(code).__name__})"
                logger.warning(f"  attempt {attempt}: {last_error}")
                continue
            previous_code = code

            # Step 1: Strict AST Audit
            is_ast_valid, violations = ASTContractAuditor.audit(code)
            if not is_ast_valid:
                failing_code = code
                last_error = f"AST Violations: {violations}"
                logger.warning(f"  attempt {attempt} failed AST validation: {violations}")
                continue

            # Step 2: Hardened Sandboxed Execution
            run_result = self.sandbox.run_isolated(code)
            if run_result["passed"]:
                logger.info(f"[self-tests passed] attempt {attempt} ran clean in the jail "
                            f"(checked by {VERIFIED_BY}).")
                self.db.save_resolution(task_hash, failing_code, code, last_error)
                return {
                    "status": "SELF_TESTS_PASSED",
                    "attempts": attempt,
                    "code": code,
                    "stdout": run_result["stdout"],
                    "verified_by": VERIFIED_BY,
                }
            failing_code = code
            last_error = run_result["stderr"] or "Non-zero exit status"
            logger.warning(f"  attempt {attempt} failed in the jail: {last_error}")

        return {
            "status": "FAILED_BUDGET_EXHAUSTED",
            "attempts": max_retries,
            "last_code": previous_code,
            "last_error": last_error
        }


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    task = (
        "Write a function `calculate_fixed_point_fee(amount_cents: int, fee_basis_pts: int) -> int` "
        "that calculates fee in cents with floor rounding. Assert fee_basis_pts >= 0 and amount_cents >= 0. "
        "Include unit tests and assertion checks."
    )
    engine = SelfHealingEngine()
    result = await engine.execute_task_with_healing(task, max_retries=3)
    print("\n" + "=" * 80)
    print("FINAL EXECUTION RESULT:")
    print("=" * 80)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
