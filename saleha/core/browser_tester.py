"""
Saleha Core: Autonomous Visual Browser UI Tester & E2E Web Agent

Executes automated end-to-end browser flows, DOM interactions (click, fill, navigate, select),
visual assertion checks, and screenshot captures for frontend web applications.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class BrowserAction:
    action_type: str        # goto | click | fill | assert_text | screenshot
    target: str             # url | css selector | expected text
    value: str = ""         # input value if fill
    timeout_ms: int = 5000


@dataclass
class BrowserStepResult:
    action: BrowserAction
    success: bool
    duration_ms: float
    screenshot_path: str = ""
    error: str = ""


@dataclass
class BrowserTestReport:
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration_sec: float
    step_results: List[BrowserStepResult] = field(default_factory=list)
    success: bool = True
    error_summary: str = ""
    # False when no browser step ran (Playwright missing, or the request was
    # rejected before launch). Such a report is never `success=True`.
    executed: bool = True


class AutonomousBrowserTester:
    """Automates headless browser UI testing, DOM assertions, and visual verification."""

    def __init__(self, headless: bool = True, screenshot_dir: str = ".saleha/screenshots"):
        self.headless = headless
        self.screenshot_dir = os.path.abspath(screenshot_dir)

    def execute_flow(self, actions: List[BrowserAction]) -> BrowserTestReport:
        """Executes a sequential list of browser actions and captures step-by-step telemetry."""
        os.makedirs(self.screenshot_dir, exist_ok=True)
        start_time = time.time()
        step_results: List[BrowserStepResult] = []
        overall_success = True
        error_summary = ""

        executed = False

        # Validate the whole request up front so a malformed action fails the
        # same way with or without a browser.
        valid_types = {"goto", "click", "fill", "assert_text", "screenshot"}
        for idx, act in enumerate(actions, 1):
            problem = ""
            if act.action_type not in valid_types:
                problem = f"Unknown action type '{act.action_type}'"
            elif not act.target and act.action_type != "screenshot":
                problem = "Action target cannot be empty"
            if problem:
                step_results.append(BrowserStepResult(action=act, success=False, duration_ms=0.0, error=problem))
                return self._report(actions, step_results, start_time, False, f"Step {idx}: {problem}", False)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            # Earlier versions "simulated" the run here: every step was reported
            # as passed, and a 'screenshot' wrote the bytes b"PNG_MOCK". Nothing
            # was ever opened, so that was a fabricated pass.
            return self._report(
                actions, step_results, start_time, False,
                "Playwright is not installed; no browser step was run "
                "(pip install playwright && playwright install chromium)", False,
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()
                executed = True

                for idx, act in enumerate(actions, 1):
                    step_start = time.time()
                    shot_path = ""
                    try:
                        if act.action_type == "goto":
                            page.goto(act.target, timeout=act.timeout_ms)
                        elif act.action_type == "click":
                            page.click(act.target, timeout=act.timeout_ms)
                        elif act.action_type == "fill":
                            page.fill(act.target, act.value, timeout=act.timeout_ms)
                        elif act.action_type == "assert_text":
                            page.wait_for_selector(f"text={act.target}", timeout=act.timeout_ms)
                        elif act.action_type == "screenshot":
                            shot_path = os.path.join(self.screenshot_dir, f"{act.target or f'step_{idx}'}.png")
                            page.screenshot(path=shot_path)

                        elapsed = (time.time() - step_start) * 1000
                        step_results.append(BrowserStepResult(
                            action=act, success=True, duration_ms=round(elapsed, 2), screenshot_path=shot_path
                        ))
                    except Exception as e:
                        elapsed = (time.time() - step_start) * 1000
                        err_msg = str(e)
                        step_results.append(BrowserStepResult(
                            action=act, success=False, duration_ms=round(elapsed, 2), error=err_msg
                        ))
                        overall_success = False
                        error_summary = f"Step {idx} ({act.action_type} '{act.target}') failed: {err_msg}"
                        break

                browser.close()
        except Exception as e:
            overall_success = False
            error_summary = f"Browser session error: {e}"

        return self._report(actions, step_results, start_time, overall_success, error_summary, executed)

    @staticmethod
    def _report(actions: List[BrowserAction], step_results: List[BrowserStepResult],
                start_time: float, success: bool, error_summary: str, executed: bool) -> BrowserTestReport:
        total_dur = round(time.time() - start_time, 3)
        return BrowserTestReport(
            total_steps=len(actions),
            passed_steps=sum(1 for s in step_results if s.success),
            failed_steps=sum(1 for s in step_results if not s.success),
            duration_sec=total_dur,
            step_results=step_results,
            success=success,
            error_summary=error_summary,
            executed=executed,
        )


# Global instance
browser_tester = AutonomousBrowserTester()
