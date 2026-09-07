"""
Saleha Core: Orchestrator (the self-healing loop).

Runs one task end to end: Planner -> Coder -> Tester -> Reviewer -> Verifier,
with a healing loop that feeds real errors back to the Debugger or Coder.

Notes on the pieces that are easy to misread:

1. StatsTracker persists every outcome (success or failure) to
   ~/.saleha/stats.json, so model performance survives a restart.
2. coder.generate_code() receives the real attempt number, so result.attempts
   reflects retries instead of always reading "1".
3. The skill registry is consulted before planning: a built-in skill (e.g. the
   calculator) can answer directly with no LLM call. Adding a skill means
   adding a file under core/skills/, not editing this orchestrator.
"""

import time
from typing import Optional

from saleha.agents.planner import PlannerAgent, PlanResult
from saleha.agents.coder import CoderAgent, CodeResult
from saleha.agents.debugger import DebuggerAgent
from saleha.agents.tester import TesterAgent, TestResult
from saleha.agents.reviewer import ReviewerAgent, ReviewResult
from saleha.core.self_healing import SelfHealingEngine, HealingResult
from saleha.core.stats_tracker import StatsTracker
from saleha.core.task_history import TaskHistory
from saleha.core.code_executor import CodeExecutor
from saleha.core.skill_registry import registry as skill_registry, load_builtin_skills
from saleha.core.agent_profile_loader import profile_registry
from saleha.core.memory_store import memory_store
from saleha.core.git_native import git_engine

load_builtin_skills()

# ==============================================================================
# 1. Data structures
# ==============================================================================

class OrchestrationResult:
    """
    Outcome of one orchestrated task.

    `verified` is the important field alongside `success`. It says whether the
    returned code was actually executed and ran clean, which is a stronger
    claim than `success` and must never be inferred from it:

      verified=True   the code ran, no runtime error
      verified=False  it was accepted without ever being executed --
                      `unverified_reason` says why

    This distinction was missing. `success=True` was returned on the
    "max attempts exhausted, accept the reviewer's objections anyway" path,
    where the verifier is never reached at all because it lives inside the
    `if review_result.approved` branch. Measured: a `1 / 0` crash was returned
    as a success with the verifier called zero times.
    """

    def __init__(self, success: bool, final_code: str, attempts: int, log: str,
                 profile_used: str = "", verified: bool = False,
                 unverified_reason: str = ""):
        self.success = success
        self.final_code = final_code
        self.attempts = attempts
        self.log = log
        self.profile_used = profile_used
        self.verified = verified
        self.unverified_reason = unverified_reason

# ==============================================================================
# 2. Core logic
# ==============================================================================

class SalehaOrchestrator:
    def __init__(self, model: str = "qwen2.5-coder:3b", max_healing_attempts: int = 3,
                 profile: Optional[str] = None, parallel_candidates: int = 0):
        """
        Initializes the multi-agent orchestrator with Planner, Coder,
        Debugger, Tester, and Reviewer.

        `parallel_candidates` (0 = off) generates N candidate solutions
        concurrently and keeps the one that actually passes the tests,
        instead of generating one and healing it in sequence. Measured on
        this box: five concurrent calls take 15.5s where five sequential
        ones take ~34s, because a local model leaves the GPU idle during
        prompt evaluation. Off by default -- it costs N times the tokens,
        which is only worth it when a wrong answer is expensive to find
        later, and `generate_tests=True` is needed for the selection to be
        by execution rather than by guess.
        """
        self.model = model
        self.parallel_candidates = max(0, parallel_candidates)
        self.planner = PlannerAgent(model=model)
        self.coder = CoderAgent(model=model, max_attempts=max_healing_attempts)
        self.debugger = DebuggerAgent(model=model)
        self.tester = TesterAgent()
        self.reviewer = ReviewerAgent(model=model)   # LLM-based code review
        self.healer = SelfHealingEngine()
        self.max_healing_attempts = max_healing_attempts
        self.default_profile = profile_registry.get(profile) if profile else None
        self.stats = StatsTracker()                  # persistence layer
        self.history = TaskHistory()                 # full record of every task
        self.verifier = CodeExecutor(timeout=15)     # runs the code to verify it
        self.last_goal: str = ""                     # previous task, session-scoped
        self.last_code: str = ""

    def execute_task(self, user_goal: str, use_context: bool = True, profile: Optional[str] = None, auto_commit: bool = False, context_dir: Optional[str] = None, generate_tests: bool = False, resume_session: bool = False, on_token=None) -> OrchestrationResult:
        """
        `use_context=True` (default): if an earlier task in this same
        orchestrator session succeeded, its code is passed to the Planner and
        Coder as context, so follow-ups like "add this to that function" work.
        The memory is session-level and resets with a new `SalehaOrchestrator()`
        -- it is not written to disk.

        `context_dir`: RepoContextPacker scans that directory and prepends
        task-relevant repository context (tree + symbols + key excerpt), within
        budget, to the Coder prompt -- Aider-style repository awareness.

        `generate_tests=True`: the Coder also generates a unittest suite, and
        the healing loop runs REAL test execution (core/test_runner.py) instead
        of static checks, feeding failure tracebacks straight to the healer.

        `resume_session=True`: loads the last in-progress checkpoint and
        continues from the verification/healing loop, skipping planning and
        coding. Used by `saleha run --resume`.
        """
        from saleha.core.session_store import session_store, SessionState
        from saleha.core.metrics import metrics_tracker
        _run_start = time.time()

        # ------------------------------------------------------------------
        # RESUME BRANCH -- checked first, so skill/memory/planner/coder are all
        # skipped and control lands directly on the verification loop.
        # ------------------------------------------------------------------
        # Initialised up front. This was previously assigned only inside the
        # `if resume_session:` branch and the `if not resumed:` branch, so
        # every later `log +=` was a possibly-unbound reference -- ten of them,
        # flagged by the type checker on every edit of this file.
        log = ""
        resumed = False
        current_test_code = ""
        task_complexity = 0.0
        _resume_code = ""
        _resume_attempts = 1
        if resume_session:
            st = session_store.load()
            if not st or st.status != "in_progress" or not st.current_code.strip():
                return OrchestrationResult(
                    success=False, final_code="", attempts=0,
                    log="No resumable in-progress session found (~/.saleha/session.json).",
                )
            user_goal = st.goal or user_goal
            profile = st.profile or None
            generate_tests = st.generate_tests
            current_test_code = st.current_test_code or ""
            task_complexity = st.complexity_score or 0.0
            _resume_code = st.current_code
            _resume_attempts = max(1, st.attempts or 1)
            resumed = True  # this flag makes the guarded blocks below skip
            log = (
                f"RESUME: '{user_goal}' (attempt {st.attempts}/{st.max_attempts}, "
                f"checkpoint {time.strftime('%H:%M:%S', time.localtime(st.updated_at))})\n"
                + "-" * 60 + "\nSaved code restored -- planning/coding skipped.\n"
            )

        if not resumed:
            # (the resume branch has already written its own header)
            log = f"Goal: {user_goal}\n" + "-" * 60

        # Resolve the active agent profile.
        #
        # On resume, the checkpoint's profile is authoritative and must not be
        # re-derived: if the saved profile was empty, `match_profile_for_task`
        # would run again here and could select a DIFFERENT profile from the
        # run being resumed -- which defeats the point of a checkpoint. So a
        # resumed run with no saved profile stays profile-less.
        if profile:
            active_profile = profile_registry.get(profile)
        elif resumed:
            active_profile = None
        else:
            active_profile = self.default_profile or profile_registry.match_profile_for_task(user_goal)
        profile_name = active_profile.id if active_profile else ""
        if active_profile:
            log += f"\nActive agent profile: {active_profile.name} [{active_profile.id}]\n"

        if not resumed:
            # Plugin hooks: on_task_start
            try:
                from saleha.core.plugin_loader import plugin_loader as _pl
                _pl.trigger_event("on_task_start", goal=user_goal)
            except Exception:
                pass

            # Ask first whether a built-in skill can answer this directly.
            matched_skill = skill_registry.find_skill(user_goal)
            if matched_skill:
                log += f"\nSkill matched: '{matched_skill.name}' -- skipping the LLM pipeline, solving directly.\n"
                skill_result = matched_skill.execute(user_goal)
                if skill_result.success:
                    log += f"{skill_result.output}\n"
                    self.history.log(goal=user_goal, model=f"skill:{matched_skill.name}",
                                      success=True, attempts=0, code=skill_result.output)
                    # A skill computes its answer directly (e.g. arithmetic);
                    # there is no generated program to execute, so `verified`
                    # stays False with the reason stated rather than implying
                    # a run that never applies here.
                    return OrchestrationResult(
                        success=True, final_code=skill_result.output, attempts=0,
                        log=log, profile_used=profile_name, verified=False,
                        unverified_reason=(
                            f"Answered directly by skill '{matched_skill.name}'; "
                            "no generated code was executed."
                        ),
                    )
                else:
                    log += f"Skill failed ({skill_result.error}); falling back to the normal pipeline.\n"
                    # the normal pipeline continues below

            # Long-term memory lookup (verified solution caching).
            # Scope the cache to this model when one is pinned. Without it,
            # benchmarking a second model on prompts a first model already
            # solved replays the first model's answer ("LLM skipped") and
            # reports it as the second model's result -- verified to produce
            # identical, meaningless before/after numbers in a real tuning run.
            #
            # "auto" is deliberately NOT passed as a filter: entries are stored
            # under the resolved model name (CodeResult.model_used), so
            # filtering on the literal string "auto" would match nothing and
            # silently disable the cache for every default-configured run.
            cached_mem = memory_store.recall(
                user_goal,
                model=self.model if self.model and self.model != "auto" else None,
            )
            if cached_mem:
                # How the cached entry was checked when it was first solved.
                # "ran_without_error" means only that it did not crash -- no
                # test suite existed for it -- so it must not be replayed under
                # the word "verified".
                cached_source = getattr(cached_mem, "source_type", "") or ""
                how_checked = ("previously verified against a test suite"
                               if cached_source == "verified_execution"
                               else "previously ran without error (no test suite)")
                log += (f"\nMemory recall: reusing a solution {how_checked} "
                        f"(hit {cached_mem.hit_count} times) -- LLM skipped.\n")
                self.history.log(goal=user_goal, model=f"memory:{cached_mem.model}",
                                  success=True, attempts=0, code=cached_mem.code)
                self.last_goal = user_goal
                self.last_code = cached_mem.code
                # Nothing was executed in THIS run either way, so `verified`
                # stays False and the reason carries both facts.
                return OrchestrationResult(
                    success=True, final_code=cached_mem.code, attempts=0, log=log,
                    profile_used="memory_store", verified=False,
                    unverified_reason=(
                        f"Replayed from memory ({how_checked}); "
                        "not re-executed in this run."
                    ),
                )

            context_note = ""
            if use_context and self.last_code:
                context_note = (
                    f"\n\n[Previous task context]\nPrevious goal: {self.last_goal}\n"
                    f"Previous code:\n{self.last_code}\n"
                    f"(If the current goal relates to this code, build on it.)"
                )

            profile_context = ""
            if active_profile:
                profile_context = f"\n\n{active_profile.format_persona_prompt()}\n"

            # Repo context packing (Aider-style): a task-relevant repo map is
            # given to the Coder within budget, for real-project awareness.
            repo_note = ""
            if context_dir:
                try:
                    from saleha.core.repo_context_packer import RepoContextPacker
                    packed = RepoContextPacker(root_dir=context_dir).pack(user_goal)
                    if packed:
                        repo_note = f"\n\n[Repository Context]\n{packed}\n"
                        log += "Repo context packed (task-relevant symbols + excerpt).\n"
                    else:
                        log += "Repo context: no relevant code file found.\n"
                except Exception as pack_err:
                    log += f"Repo context packing failed (non-fatal): {pack_err}\n"

            # Step 1: ask the Planner for a plan.
            log += "\n[1/4] Planner: building a plan...\n"
            plan_result: PlanResult = self.planner.create_plan(user_goal + profile_context)

            if not plan_result.success:
                # A goal too vague to act on is not a planning failure -- it is
                # a question. Reporting "Planning Failed" for it would hide the
                # one thing the user can actually do about it.
                if getattr(plan_result, "needs_clarification", False):
                    question = plan_result.clarifying_question or plan_result.raw_response
                    why = "\n".join(f"   - {r}" for r in plan_result.uncertainty_reasons)
                    self.history.log(goal=user_goal, model=self.model, success=False,
                                     attempts=0, code="",
                                     error=f"Needs clarification: {question}")
                    return OrchestrationResult(
                        success=False, final_code="", attempts=0,
                        log=log + f"I need one detail before I start:\n   {question}\n"
                                  f"{chr(10) + 'Why:' + chr(10) + why if why else ''}",
                        profile_used=profile_name
                    )
                self.stats.record(model=self.model, success=False, attempts=0, task_type="coding")
                self.history.log(goal=user_goal, model=self.model, success=False, attempts=0,
                                  code="", error=f"Planning failed: {plan_result.raw_response}")
                return OrchestrationResult(
                    success=False, final_code="", attempts=0,
                    log=log + f"Planning failed: {plan_result.raw_response}",
                    profile_used=profile_name
                )

            log += f"Plan ready (recommendation: {plan_result.recommendation})\n"

            # Step 2: ask the Coder for code (first attempt).
            # The Planner's complexity score now reaches SmartRouter, so
            # complexity-tiered model selection actually takes effect.
            task_complexity = getattr(plan_result, "complexity_score", 0.0) or 0.0
            # Parallel candidate selection needs a test suite to select
            # WITH, and generate_tests() needs code to write tests against
            # -- it returns "No runnable tests found" when handed an empty
            # string (verified). So the order is: one cheap draft, tests
            # written against that draft, then N candidates raced against
            # those tests. The draft is a real candidate itself, not thrown
            # away, so the extra call is not wasted.
            current_test_code = ""
            draft_result = None
            if self.parallel_candidates > 1 and generate_tests:
                log += "\n[2a] Coder: draft + unittest suite (for candidate selection)...\n"
                draft_result = self.coder.generate_code(
                    user_goal + profile_context,
                    plan="\n".join(plan_result.steps[:3]) + context_note + repo_note,
                    attempt=1, complexity_score=task_complexity,
                )
                if draft_result.success and draft_result.code.strip():
                    pre_tests = self.coder.generate_tests(
                        draft_result.code, goal=user_goal,
                        complexity_score=task_complexity)
                    if pre_tests.success and pre_tests.code.strip():
                        current_test_code = self.healer.auto_patch_code(pre_tests.code)
                        log += (f"Test suite ready "
                                f"({len(current_test_code.splitlines())} lines).\n")
                    else:
                        log += "Test generation failed -- parallel selection skipped.\n"
                else:
                    log += "Draft failed -- parallel selection skipped.\n"

            log += "\n[2/4] Coder: generating code...\n"

            # Parallel candidate generation, when asked for AND when there
            # is a real test suite to select with. Without tests the choice
            # would be structural guesswork, which is worse than one honest
            # attempt -- so this deliberately does not run in that case.
            current_code_result = None
            if self.parallel_candidates > 1 and generate_tests and current_test_code:
                try:
                    from saleha.core.parallel_solver import ParallelSolver
                    solver = ParallelSolver(model=self.model,
                                            candidates=self.parallel_candidates)
                    par = solver.solve_with_executor(
                        goal=user_goal + profile_context,
                        test_suite=current_test_code,
                        context="\n".join(plan_result.steps[:3]) + context_note + repo_note,
                    )
                    passed = sum(1 for c in par.candidates if c.passed)
                    log += (f"   {len(par.candidates)} candidates in parallel "
                            f"({par.total_latency_sec}s): {passed} passed tests\n")
                    if par.verified:
                        log += f"   {par.reason}\n"
                        current_code_result = CodeResult(
                            success=True, code=par.code,
                            model_used=self.model, attempts=1,
                        )
                    else:
                        # Every candidate failed. Before falling back, try
                        # the draft -- it was generated anyway and is a real
                        # candidate, so discarding it untested would waste a
                        # call already paid for.
                        if draft_result is not None and draft_result.code.strip():
                            chk = self.verifier.execute(
                                f"{draft_result.code}\n\n{current_test_code}")
                            if getattr(chk, "success", False) and (
                                    "TEST_PASSED" not in current_test_code
                                    or "TEST_PASSED" in (getattr(chk, "output", "") or "")):
                                log += "   draft passed the suite; using it\n"
                                current_code_result = draft_result
                        if current_code_result is None:
                            # Nothing verified. Fall through to the normal
                            # single-shot path plus healing rather than
                            # returning an unverified candidate as if it worked.
                            log += f"   {par.reason} -- falling back to single-shot\n"
                except Exception as exc:
                    log += f"   parallel generation unavailable ({exc}); single-shot\n"

            if current_code_result is None:
                current_code_result = self.coder.generate_code(
                    user_goal + profile_context,
                    plan="\n".join(plan_result.steps[:3]) + context_note + repo_note,
                    attempt=1,
                    complexity_score=task_complexity,
                    on_token=on_token,
                )

            if not current_code_result.success:
                self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=1, task_type="coding")
                self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                  success=False, attempts=1, code="", error=current_code_result.error)
                return OrchestrationResult(
                    success=False, final_code="", attempts=1,
                    log=log + f"Coding failed: {current_code_result.error}",
                    profile_used=profile_name
                )

            current_code = self.healer.auto_patch_code(current_code_result.code)
            attempts = 1
            log += f"Code generated (attempt {attempts})\n"

            # Optional REAL test suite generation. Without it the healing loop
            # only ran static checks and never executed a unittest.
            # NOTE: no reset to "" here. When parallel candidates ran, the
            # suite was already generated above and used to select the
            # winner; clearing it would throw away a working suite and
            # regenerate it for no reason.
            if generate_tests and not current_test_code:
                log += "\n[2b] Coder: generating unittest suite...\n"
                tests_result = self.coder.generate_tests(
                    current_code, goal=user_goal, complexity_score=task_complexity
                )
                if tests_result.success and tests_result.code.strip():
                    current_test_code = self.healer.auto_patch_code(tests_result.code)
                    log += f"Test suite ready ({len(current_test_code.splitlines())} lines).\n"
                else:
                    log += f"Test generation failed: {tests_result.error} -- falling back to static checks.\n"
        else:
            # Resume: restore saved artifacts.
            current_code = _resume_code
            attempts = min(_resume_attempts, self.max_healing_attempts)
            # The loop reads current_code_result.model_used for stats and
            # logging, so build a synthetic result when resuming.
            current_code_result = CodeResult(
                success=True, code=current_code, attempts=attempts,
                model_used="resumed-session",
            )

        def _checkpoint(status: str = "in_progress"):
            """Crash-recovery checkpoint (~/.saleha/session.json)."""
            session_store.save(SessionState(
                goal=user_goal,
                model=self.model,
                profile=profile_name,
                context_dir=context_dir or "",
                generate_tests=bool(current_test_code) or generate_tests,
                attempts=attempts,
                max_attempts=self.max_healing_attempts,
                current_code=current_code,
                current_test_code=current_test_code,
                complexity_score=task_complexity,
                status=status,
            ))
            # Terminal outcomes also go to the structured metrics tracker.
            if status in ("completed", "failed"):
                metrics_tracker.record(
                    "run_completed",
                    success=(status == "completed"),
                    attempts=attempts,
                    model=getattr(current_code_result, "model_used", "") or self.model,
                    profile=profile_name,
                    had_tests=bool(current_test_code),
                    duration_sec=round(time.time() - _run_start, 2),
                    tokens_used=int(getattr(self.coder, "total_tokens_used", 0) or 0),
                )

        if current_code.strip():
            _checkpoint("in_progress")

        # Plugin hook: on_code_generated. External plugins receive real
        # pipeline events (the loader existed before but never fired).
        try:
            from saleha.core.plugin_loader import plugin_loader
            plugin_loader.trigger_event("on_code_generated", code=current_code, goal=user_goal)
        except Exception:
            pass

        # Step 3 & 4: Self-Healing Loop (Tester -> Healer -> Coder)
        while attempts <= self.max_healing_attempts:
            log += f"\n[3/4] Tester: checking the code (attempt {attempts})...\n"

            if current_test_code:
                # REAL test execution: the unittest suite runs in the sandbox.
                suite_res = self.tester.run_suite(current_code, test_code=current_test_code)
                test_result = TestResult(
                    passed=suite_res.passed,
                    error_message="" if suite_res.passed else (
                        f"Test Suite Failed ({suite_res.summary})\n"
                        f"{suite_res.failure_report()}"
                    ),
                    error_type="TestFailure" if not suite_res.passed else "None",
                )
            else:
                test_result: TestResult = self.tester.test_code(current_code)

            if test_result.passed:
                log += "\n[4/5] Tester: code is safe and syntactically valid.\n"
                log += f"\n[5/5] Reviewer: reviewing the code (attempt {attempts})...\n"
                review_result: ReviewResult = self.reviewer.review_code(user_goal, current_code)

                if review_result.approved:
                    log += "Reviewer approved.\n"
                    log += f"\n[6/6] Verifier: running the code to check it...\n"
                    exec_result = self.verifier.execute(current_code)

                    if exec_result.blocked:
                        # A dangerous pattern cannot be fixed by retrying:
                        # fail immediately rather than looping.
                        log += f"Verifier blocked execution: {exec_result.block_reason}\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=False, attempts=attempts, code=current_code,
                                          error=f"Blocked: {exec_result.block_reason}")
                        # This exit had no checkpoint, so the session stayed
                        # "in_progress" and `saleha run --resume` would pick a
                        # blocked task back up. It also meant blocked runs never
                        # reached metrics_tracker (which _checkpoint calls on a
                        # terminal status), so they were invisible in metrics and
                        # the recorded success rate read higher than reality.
                        _checkpoint("failed")
                        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                    if exec_result.success:
                        log += "Code ran successfully with no runtime error.\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=True, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=True, attempts=attempts, code=current_code)
                        try:
                            # Record HOW this was verified, not just that it
                            # was. Without a generated test suite the only
                            # check that ran is "the code did not crash", which
                            # is much weaker than a passing test run -- and the
                            # recall path advertises these entries as
                            # "previously verified solution". Storing the
                            # distinction keeps that claim honest.
                            memory_store.remember(
                                goal=user_goal,
                                code=current_code,
                                model=current_code_result.model_used or self.model,
                                source_type=("verified_execution"
                                             if current_test_code
                                             else "ran_without_error"),
                            )
                        except (IOError, OSError, TypeError) as e:
                            log += f"   Warning: Memory store save failed: {e}\n"

                        if auto_commit and git_engine.is_git_repo():
                            # This pipeline returns generated code; it never
                            # writes it to a file. So there is no file list of
                            # "what the agent changed" to stage.
                            #
                            # This call used to pass no files, which made
                            # auto_commit_task run `git add .` -- committing
                            # every unrelated uncommitted change in the user's
                            # working tree under a message describing the
                            # agent's task. It also hardcoded test_passed=True,
                            # so the message claimed tests passed even when
                            # generate_tests was False and no suite existed.
                            #
                            # Staging everything is now opt-in and deliberate,
                            # and test_passed reflects whether a real suite ran.
                            commit_res = git_engine.auto_commit_task(
                                goal=user_goal,
                                task_type="feat",
                                model=current_code_result.model_used or self.model,
                                test_passed=bool(current_test_code),
                                allow_stage_all=True,
                            )
                            if commit_res.success:
                                log += f"\nGit auto-commit: [{commit_res.commit_hash}] {commit_res.message.splitlines()[0]}\n"
                            else:
                                log += f"\nGit auto-commit skipped: {commit_res.error}\n"

                        self.last_goal = user_goal
                        self.last_code = current_code
                        _checkpoint("completed")
                        try:
                            from saleha.core.plugin_loader import plugin_loader as _pl2
                            _pl2.trigger_event("on_test_complete", result="passed", goal=user_goal)
                        except Exception:
                            pass
                        return OrchestrationResult(
                            success=True, final_code=current_code, attempts=attempts,
                            log=log, profile_used=profile_name, verified=True,
                        )

                    # Execution failed: syntax and review were fine, but it
                    # crashed at runtime.
                    log += f"Verifier: execution failed: {exec_result.error}\n"

                    if attempts < self.max_healing_attempts:
                        log += "   Sending the real runtime error to the Debugger...\n"
                        next_attempt = attempts + 1
                        debug_result = self.debugger.debug_code(
                            task=user_goal,
                            code=current_code,
                            error_log=exec_result.error,
                        )
                        if debug_result.success:
                            current_code_result = CodeResult(
                                success=True,
                                code=debug_result.fixed_code,
                                attempts=next_attempt,
                                model_used=debug_result.model_used,
                            )
                        else:
                            log += f"   Debugger failed: {debug_result.error}; falling back to the Coder.\n"
                            current_code_result = self.coder.generate_code(
                                task=user_goal,
                                plan=f"Previous code:\n{current_code}\n\nRunning it produced this real error:\n{exec_result.error}\n\nFix it.",
                                attempt=next_attempt,
                                complexity_score=task_complexity,
                            )
                        if current_code_result.success:
                            current_code = self.healer.auto_patch_code(current_code_result.code)
                            attempts = next_attempt
                            continue  # re-run tester + reviewer + verifier
                        else:
                            log += f"Coder failed to fix it: {current_code_result.error}\n"
                            break
                    else:
                        log += "Max attempts reached -- accepting with the execution error (best-effort).\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=False, attempts=attempts, code=current_code,
                                          error=f"Execution failed: {exec_result.error}")
                        _checkpoint("failed")
                        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                log += f"Reviewer feedback: {review_result.feedback}\n"

                if attempts < self.max_healing_attempts:
                    log += "   Sending the review feedback back to the Coder...\n"
                    next_attempt = attempts + 1
                    current_code_result = self.coder.generate_code(
                        task=user_goal,
                        plan=f"Previous code:\n{current_code}\n\nReviewer feedback:\n{review_result.feedback}",
                        attempt=next_attempt,
                        complexity_score=task_complexity,
                    )
                    if current_code_result.success:
                        current_code = self.healer.auto_patch_code(current_code_result.code)
                        attempts = next_attempt
                        continue  # re-run tester + reviewer
                    else:
                        log += f"Coder failed to fix it: {current_code_result.error}\n"
                        break
                else:
                    # Max attempts reached and the reviewer never approved.
                    #
                    # This used to return success=True directly. The verifier
                    # call sits inside `if review_result.approved`, so on this
                    # path the code was NEVER executed -- measured: a `1 / 0`
                    # crash came back as a success with the verifier called
                    # zero times.
                    #
                    # It is now executed before being accepted. Best-effort
                    # acceptance is fine; calling it "success" unrun is not.
                    log += "Max attempts reached -- verifying before accepting without reviewer approval...\n"
                    final_exec = self.verifier.execute(current_code)

                    if final_exec.blocked:
                        log += f"Verifier blocked execution: {final_exec.block_reason}\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=False, attempts=attempts, code=current_code,
                                          error=f"Blocked: {final_exec.block_reason}")
                        _checkpoint("failed")
                        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                    if not final_exec.success:
                        log += f"Reviewer did not approve AND the code failed to run: {final_exec.error}\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=False, attempts=attempts, code=current_code,
                                          error=f"Unapproved and execution failed: {final_exec.error}")
                        _checkpoint("failed")
                        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                    log += "Code ran, but the reviewer objection is unresolved (best-effort accept).\n"
                    self.stats.record(model=current_code_result.model_used or self.model, success=True, attempts=attempts, task_type="coding")
                    self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                      success=True, attempts=attempts, code=current_code,
                                      error=f"Accepted without review approval: {review_result.feedback}")
                    self.last_goal = user_goal
                    self.last_code = current_code
                    _checkpoint("completed")
                    return OrchestrationResult(
                        success=True, final_code=current_code, attempts=attempts,
                        log=log, profile_used=profile_name, verified=True,
                        unverified_reason=(
                            "Code executed cleanly, but the reviewer's objection "
                            f"was never resolved: {review_result.feedback}"
                        ),
                    )

            log += f"Tester failed: {test_result.error_type}\n"
            log += f"   Reason: {test_result.error_message}\n"

            if attempts < self.max_healing_attempts:
                log += f"\n[4/4] Healer: analysing the error and instructing the Coder...\n"
                healing_result: HealingResult = self.healer.analyze_and_heal(test_result.error_message, user_goal)

                log += f"   Identified error: {healing_result.error_type}\n"
                log += "   Sending a new prompt to the Coder...\n"

                next_attempt = attempts + 1
                current_code_result = self.coder.generate_code(
                    task=user_goal,
                    plan=f"Previous code:\n{current_code}\n\nFix instructions:\n{healing_result.reflexion_prompt}",
                    attempt=next_attempt,
                    complexity_score=task_complexity,
                )

                if current_code_result.success:
                    current_code = self.healer.auto_patch_code(current_code_result.code)
                    attempts = next_attempt
                else:
                    log += f"Coder failed to fix it: {current_code_result.error}\n"
                    break
            else:
                log += f"\nMaximum self-healing attempts ({self.max_healing_attempts}) exhausted. Task failed.\n"
                break

        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                          success=False, attempts=attempts, code=current_code,
                          error="Max healing attempts reached")
        _checkpoint("failed")
        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

    def execute_with_tot_exploration(self, goal: str, initial_code: str, test_suite: str, max_depth: int = 3, branching_factor: int = 3):
        """Executes advanced Tree-of-Thoughts (ToT) search with backtracking and learned heuristics."""
        from saleha.core.tot_orchestrator import tot_orchestrator
        return tot_orchestrator.solve_task_with_tot(
            goal=goal,
            initial_code=initial_code,
            test_suite=test_suite,
            max_depth=max_depth,
            branching_factor=branching_factor
        )

# ==============================================================================
# 3. Testing
# ==============================================================================

if __name__ == "__main__":
    _orchestrator = SalehaOrchestrator(model="qwen2.5-coder:3b", max_healing_attempts=3)
    _res = _orchestrator.execute_task("def add(a, b): return a + b")