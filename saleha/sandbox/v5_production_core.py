import os
import sys
import json
import time
import sqlite3
import logging
import asyncio
from typing import Dict, Any, Optional
from local_llm_driver import LocalLLMDriver
from ast_security_verifier import ASTContractAuditor
from sandbox_jail import HardenedSandbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("V5_ProductionEngine")

class PersistentSwarmDB:
    def __init__(self, db_path: str = "swarm_memory.sqlite3"):
        self.conn = sqlite3.connect(db_path)
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
    def __init__(self, specs_dir: str = "../01_agent_specs"):
        self.specs_dir = specs_dir
        os.makedirs(specs_dir, exist_ok=True)

    def agent_exists(self, domain_key: str) -> bool:
        norm = domain_key.lower().replace(" ", "_")
        for f in os.listdir(self.specs_dir):
            if norm in f:
                return True
        return False

    async def generate_agent_persona(self, domain: str, requirement: str, llm: LocalLLMDriver) -> str:
        logger.info(f"Capability Gap: Dynamically synthesizing persona for '{domain}'...")
        prompt = f"""
Write an Agent Specification in Markdown format with YAML frontmatter.
Domain: {domain}
Core Goal: {requirement}

Required structure:
---
id: "agent_{domain.lower().replace(' ', '_')}"
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

        filename = f"agent_{domain.lower().replace(' ', '_')}.md"
        filepath = os.path.join(self.specs_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.get("raw_text", "").strip() + "\n")

        logger.info(f"Persona registered: {filepath}")
        return filepath


class SelfHealingEngine:
    def __init__(self):
        self.llm = LocalLLMDriver()
        self.sandbox = HardenedSandbox(max_mem_mb=128, max_cpu_sec=3)
        self.db = PersistentSwarmDB()
        self.registry = SwarmGenesisRegistry()

    async def execute_task_with_healing(self, task_spec: str, max_retries: int = 3) -> Dict[str, Any]:
        task_hash = str(abs(hash(task_spec)))

        # 1. Check persistent memory cache
        cached_fix = self.db.get_past_solution(task_hash)
        if cached_fix:
            logger.info("⚡ [Cache Hit] Found previous verified solution in SQLite. Running verification...")
            res = self.sandbox.run_isolated(cached_fix)
            if res["passed"]:
                return {"status": "RESOLVED_FROM_MEMORY", "attempts": 0, "code": cached_fix, "stdout": res["stdout"]}

        previous_code = ""
        last_error = ""

        for attempt in range(1, max_retries + 1):
            logger.info(f"🔄 [Healing Loop] Attempt {attempt}/{max_retries}...")

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
            code = structured_resp.get("code", "")
            previous_code = code

            # Step 1: Strict AST Audit
            is_ast_valid, violations = ASTContractAuditor.audit(code)
            if not is_ast_valid:
                last_error = f"AST Violations: {violations}"
                logger.warning(f"  └─ Attempt {attempt} failed AST validation: {violations}")
                continue

            # Step 2: Hardened Sandboxed Execution
            run_result = self.sandbox.run_isolated(code)
            if run_result["passed"]:
                logger.info(f"✅ [Passed] Verified code in sandbox on attempt {attempt}.")
                self.db.save_resolution(task_hash, previous_code, code, last_error)
                return {
                    "status": "PASSED",
                    "attempts": attempt,
                    "code": code,
                    "stdout": run_result["stdout"]
                }
            else:
                last_error = run_result["stderr"] or "Non-zero exit status"
                logger.warning(f"  └─ Attempt {attempt} failed runtime sandbox: {last_error}")

        return {
            "status": "FAILED_BUDGET_EXHAUSTED",
            "attempts": max_retries,
            "last_code": previous_code,
            "last_error": last_error
        }

async def main():
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
