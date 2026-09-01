"""
Saleha Core: Orchestrator (The Self-Healing Loop) -- Fixed Version

Naya kya hai vs pehle:
1. StatsTracker jud gaya hai -- har task complete hone par (success ho ya
   fail) model ka result ~/.saleha/stats.json me save hota hai. Ab restart
   ke baad bhi Saleha ko yaad rahega kaunsa model kaisa perform kar raha hai.
2. coder.generate_code() ko ab sahi attempt number pass kiya jaata hai, taaki
   result.attempts hamesha "1" na dikhaye jab retries ho rahi ho.
3. Skill registry jud gayi -- Plan/Code shuru karne se pehle check hota hai
   ki koi built-in skill (jaise calculator) is task ko seedha handle kar
   sakta hai bina LLM call kiye. Naya skill add karna ho to orchestrator
   nahi chhedna padta, bas core/skills/ me naya file banao.
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
from saleha.core.agent_profile_loader import profile_registry, AgentProfile, ProfileAgent
from saleha.core.memory_store import memory_store
from saleha.core.git_native import git_engine

load_builtin_skills()

# ==============================================================================
# 1. डेटा स्ट्रक्चर्स
# ==============================================================================

class OrchestrationResult:
    def __init__(self, success: bool, final_code: str, attempts: int, log: str, profile_used: str = ""):
        self.success = success
        self.final_code = final_code
        self.attempts = attempts
        self.log = log
        self.profile_used = profile_used

# ==============================================================================
# 2. कोर लॉजिक (Core Logic)
# ==============================================================================

class SalehaOrchestrator:
    def __init__(self, model: str = "qwen2.5-coder:1.5b", max_healing_attempts: int = 3, profile: Optional[str] = None):
        """Initializes the multi-agent orchestrator with Planner, Coder, Debugger, Tester, and Reviewer."""
        self.model = model
        self.planner = PlannerAgent(model=model)
        self.coder = CoderAgent(model=model, max_attempts=max_healing_attempts)
        self.debugger = DebuggerAgent(model=model)
        self.tester = TesterAgent()
        self.reviewer = ReviewerAgent(model=model)  # naya: LLM-based code review
        self.healer = SelfHealingEngine()
        self.max_healing_attempts = max_healing_attempts
        self.default_profile = profile_registry.get(profile) if profile else None
        self.stats = StatsTracker()  # naya: persistence layer
        self.history = TaskHistory()  # naya: har task ka poora record
        self.verifier = CodeExecutor(timeout=15)  # naya: code ko actually chala ke verify karna
        self.last_goal: str = ""  # naya: pichla task yaad rakhne ke liye (session ke andar)
        self.last_code: str = ""

    def execute_task(self, user_goal: str, use_context: bool = True, profile: Optional[str] = None, auto_commit: bool = False, context_dir: Optional[str] = None, generate_tests: bool = False, resume_session: bool = False, on_token=None) -> OrchestrationResult:
        """
        `use_context=True` (default) ka matlab: agar isi orchestrator session
        me pehle koi task successful hua tha, uska code context ke roop me
        Planner/Coder ko diya jaata hai -- taaki "usi function me ye add karo"
        jaisi follow-up requests kaam karein. Ek naya `SalehaOrchestrator()`
        banane par ye memory reset ho jaati hai (session-level hai, disk pe
        save nahi hoti).

        `context_dir` diya jaye to RepoContextPacker us directory ko scan
        karke task-relevant repo context (tree + symbols + key excerpt)
        budget ke andar Coder prompt me prepend karta hai -- Aider-style
        repository awareness.

        `generate_tests=True`: Coder se unittest suite bhi generate hoti hai,
        aur healing loop STATIC checks ki jagah REAL test execution use karta
        hai (core/test_runner.py) -- failure tracebacks seedha healer ko.

        `resume_session=True`: pichla in-progress checkpoint load karke
        verification/healing loop se continue karta hai (A4) -- planning aur
        coding skip. `saleha run --resume` isko use karta hai.
        """
        from saleha.core.session_store import session_store, SessionState
        from saleha.core.metrics import metrics_tracker
        _run_start = time.time()

        # ------------------------------------------------------------------
        # A4: RESUME BRANCH -- sabse pehle, taaki skill/memory/planner/coder
        # sab skip ho jayein aur seedha verification loop par pahunche.
        # ------------------------------------------------------------------
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
                    log="⏯️ Koi resumable in-progress session nahi mila (~/.saleha/session.json).",
                )
            user_goal = st.goal or user_goal
            profile = st.profile or None
            generate_tests = st.generate_tests
            current_test_code = st.current_test_code or ""
            task_complexity = st.complexity_score or 0.0
            _resume_code = st.current_code
            _resume_attempts = max(1, int(st.attempts or 1))
            resumed = True  # <-- yehi flag guard blocks ko skip karata hai
            log = (
                f"⏯️ RESUME: '{user_goal}' (attempt {st.attempts}/{st.max_attempts}, "
                f"checkpoint {time.strftime('%H:%M:%S', time.localtime(st.updated_at))})\n"
                + "-" * 60 + "\n✅ Saved code restore ho gaya -- planning/coding skip.\n"
            )

        if not resumed:
            # (resume branch apna header set kar chuka hota hai)
            log = f"🎯 लक्ष्य: {user_goal}\n" + "-" * 60

        # Resolve active agent profile if explicitly specified or matched
        active_profile = profile_registry.get(profile) if profile else (self.default_profile or profile_registry.match_profile_for_task(user_goal))
        profile_name = active_profile.id if active_profile else ""
        if active_profile:
            log += f"\n🎭 Active Agent Profile: {active_profile.name} [{active_profile.id}]\n"

        if not resumed:
            # Plugin hooks: on_task_start
            try:
                from saleha.core.plugin_loader import plugin_loader as _pl
                _pl.trigger_event("on_task_start", goal=user_goal)
            except Exception:
                pass

            # Naya: pehle poocho ki koi built-in skill isko seedha handle kar sakta hai
            matched_skill = skill_registry.find_skill(user_goal)
            if matched_skill:
                log += f"\n⚡ Skill matched: '{matched_skill.name}' -- LLM pipeline skip, seedha solve kiya ja raha hai.\n"
                skill_result = matched_skill.execute(user_goal)
                if skill_result.success:
                    log += f"✅ {skill_result.output}\n"
                    self.history.log(goal=user_goal, model=f"skill:{matched_skill.name}",
                                      success=True, attempts=0, code=skill_result.output)
                    return OrchestrationResult(success=True, final_code=skill_result.output, attempts=0, log=log, profile_used=profile_name)
                else:
                    log += f"⚠️ Skill fail hui ({skill_result.error}), normal pipeline pe fallback ho raha hai.\n"
                    # aage normal pipeline chalega

            # Naya: Long-term memory lookup (verified solution caching)
            cached_mem = memory_store.recall(user_goal)
            if cached_mem:
                log += f"\n🧠 Memory Recall: Found previously verified solution (Reused {cached_mem.hit_count} times) -- LLM skipped.\n"
                self.history.log(goal=user_goal, model=f"memory:{cached_mem.model}",
                                  success=True, attempts=0, code=cached_mem.code)
                self.last_goal = user_goal
                self.last_code = cached_mem.code
                return OrchestrationResult(success=True, final_code=cached_mem.code, attempts=0, log=log, profile_used="memory_store")

            context_note = ""
            if use_context and self.last_code:
                context_note = (
                    f"\n\n[पिछला Task Context]\nपिछला लक्ष्य: {self.last_goal}\n"
                    f"पिछला कोड:\n{self.last_code}\n"
                    f"(अगर वर्तमान लक्ष्य इस पिछले कोड से संबंधित है, तो उसी पर आगे बढ़ें।)"
                )

            profile_context = ""
            if active_profile:
                profile_context = f"\n\n{active_profile.format_persona_prompt()}\n"

            # Naya: Repo Context Packing (Aider-style) -- task-relevant repo map
            # budget ke andar Coder ko diya jaata hai, real-project awareness ke liye.
            repo_note = ""
            if context_dir:
                try:
                    from saleha.core.repo_context_packer import RepoContextPacker
                    packed = RepoContextPacker(root_dir=context_dir).pack(user_goal)
                    if packed:
                        repo_note = f"\n\n[Repository Context]\n{packed}\n"
                        log += "📦 Repo context packed (task-relevant symbols + excerpt).\n"
                    else:
                        log += "📦 Repo context: koi relevant code file nahi mili.\n"
                except Exception as pack_err:
                    log += f"⚠️ Repo context packing failed (non-fatal): {pack_err}\n"

            # Step 1: Planner से योजना लें
            log += "\n[1/4] Planner: योजना बना रहा है...\n"
            plan_result: PlanResult = self.planner.create_plan(user_goal + profile_context)

            if not plan_result.success:
                self.stats.record(model=self.model, success=False, attempts=0, task_type="coding")
                self.history.log(goal=user_goal, model=self.model, success=False, attempts=0,
                                  code="", error=f"Planning failed: {plan_result.raw_response}")
                return OrchestrationResult(
                    success=False, final_code="", attempts=0,
                    log=log + f"❌ Planning Failed: {plan_result.raw_response}",
                    profile_used=profile_name
                )

            log += f"✅ योजना बनी (Recommendation: {plan_result.recommendation})\n"

            # Step 2: Coder से कोड लें (पहला प्रयास)
            # Planner ka complexity score ab SmartRouter tak jaata hai --
            # complexity-tiered model selection ab actually kaam karti hai.
            task_complexity = getattr(plan_result, "complexity_score", 0.0) or 0.0
            log += "\n[2/4] Coder: कोड जनरेट कर रहा है...\n"
            current_code_result: CodeResult = self.coder.generate_code(
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
                    log=log + f"❌ Coding Failed: {current_code_result.error}",
                    profile_used=profile_name
                )

            current_code = self.healer.auto_patch_code(current_code_result.code)
            attempts = 1
            log += f"✅ कोड जनरेट हुआ (प्रयास {attempts})\n"

            # Naya (A1): optional REAL test suite generation -- inke bina healing
            # loop sirf static checks dekhta tha, unittest kabhi nahi chalti thi.
            current_test_code = ""
            if generate_tests:
                log += "\n[2b] Coder: unittest suite बना रहा है...\n"
                tests_result = self.coder.generate_tests(
                    current_code, goal=user_goal, complexity_score=task_complexity
                )
                if tests_result.success and tests_result.code.strip():
                    current_test_code = self.healer.auto_patch_code(tests_result.code)
                    log += f"✅ Test suite ready ({len(current_test_code.splitlines())} lines).\n"
                else:
                    log += f"⚠️ Test generation failed: {tests_result.error} -- static checks पर fallback.\n"
        else:
            # A4 resume: saved artifacts restore
            current_code = _resume_code
            attempts = min(_resume_attempts, self.max_healing_attempts)
            # Loop ke andar stats/log current_code_result.model_used use karte
            # hain -- resume par synthetic result bana do.
            current_code_result = CodeResult(
                success=True, code=current_code, attempts=attempts,
                model_used="resumed-session",
            )

        def _checkpoint(status: str = "in_progress"):
            """A4: crash-recovery checkpoint (~/.saleha/session.json)."""
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
            # B3: terminal outcomes structured metrics me bhi jaate hain
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

        # Plugin hooks (v1.1): on_code_generated -- external plugins ab real
        # pipeline events de sakte hain (pehle loader tha par kabhi fire nahi hota)
        try:
            from saleha.core.plugin_loader import plugin_loader
            plugin_loader.trigger_event("on_code_generated", code=current_code, goal=user_goal)
        except Exception:
            pass

        # Step 3 & 4: Self-Healing Loop (Tester -> Healer -> Coder)
        while attempts <= self.max_healing_attempts:
            log += f"\n[3/4] Tester: कोड की जाँच कर रहा है (प्रयास {attempts})...\n"

            if current_test_code:
                # REAL test execution (A1): unittest suite sandbox me chalti hai
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
                log += "\n[4/5] Tester: ✅ कोड सुरक्षित और सिंटैक्टिकली सही है।\n"
                log += f"\n[5/5] Reviewer: कोड की समीक्षा कर रहा है (प्रयास {attempts})...\n"
                review_result: ReviewResult = self.reviewer.review_code(user_goal, current_code)

                if review_result.approved:
                    log += "✅ Reviewer ने भी मंजूरी दे दी।\n"
                    log += f"\n[6/6] Verifier: कोड को actually चला कर जाँच रहा है...\n"
                    exec_result = self.verifier.execute(current_code)

                    if exec_result.blocked:
                        # Dangerous pattern -- ise retry se theek nahi kiya ja sakta,
                        # seedha fail karo, aage mat badho
                        log += f"🚫 Verifier ne block kar diya: {exec_result.block_reason}\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=False, attempts=attempts, code=current_code,
                                          error=f"Blocked: {exec_result.block_reason}")
                        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                    if exec_result.success:
                        log += "✅ Code actually chal gaya, koi runtime error nahi.\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=True, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=True, attempts=attempts, code=current_code)
                        try:
                            memory_store.remember(
                                goal=user_goal,
                                code=current_code,
                                model=current_code_result.model_used or self.model
                            )
                        except (IOError, OSError, TypeError) as e:
                            log += f"   Warning: Memory store save failed: {e}\n"

                        if auto_commit and git_engine.is_git_repo():
                            commit_res = git_engine.auto_commit_task(
                                goal=user_goal,
                                task_type="feat",
                                model=current_code_result.model_used or self.model,
                                test_passed=True
                            )
                            if commit_res.success:
                                log += f"\n🌿 Git Auto-Commit: [{commit_res.commit_hash}] {commit_res.message.splitlines()[0]}\n"
                            else:
                                log += f"\n⚠️ Git Auto-Commit skipped: {commit_res.error}\n"

                        self.last_goal = user_goal
                        self.last_code = current_code
                        _checkpoint("completed")
                        try:
                            from saleha.core.plugin_loader import plugin_loader as _pl2
                            _pl2.trigger_event("on_test_complete", result="passed", goal=user_goal)
                        except Exception:
                            pass
                        return OrchestrationResult(success=True, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                    # Execution fail hui -- syntax/review sahi tha lekin runtime pe crash hua
                    log += f"❌ Verifier: Execution fail hui: {exec_result.error}\n"

                    if attempts < self.max_healing_attempts:
                        log += "   Debugger ko actual runtime error ke saath bheja ja raha hai...\n"
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
                            log += f"   Debugger failed: {debug_result.error}; Coder fallback use hoga.\n"
                            current_code_result = self.coder.generate_code(
                                task=user_goal,
                                plan=f"पिछला कोड:\n{current_code}\n\nये कोड चलाने पर ये असली एरर आया:\n{exec_result.error}\n\nइसे ठीक करो।",
                                attempt=next_attempt,
                                complexity_score=task_complexity,
                            )
                        if current_code_result.success:
                            current_code = self.healer.auto_patch_code(current_code_result.code)
                            attempts = next_attempt
                            continue  # tester + reviewer + verifier se dobara guzro
                        else:
                            log += f"❌ Coder ने सुधारने में विफल रहे: {current_code_result.error}\n"
                            break
                    else:
                        log += "🚫 Max attempts khatam -- execution error ke saath hi accept kar rahe hain (best-effort).\n"
                        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
                        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                          success=False, attempts=attempts, code=current_code,
                                          error=f"Execution failed: {exec_result.error}")
                        _checkpoint("failed")
                        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

                log += f"⚠️ Reviewer Feedback: {review_result.feedback}\n"

                if attempts < self.max_healing_attempts:
                    log += "   Coder को review feedback के साथ दोबारा भेजा जा रहा है...\n"
                    next_attempt = attempts + 1
                    current_code_result = self.coder.generate_code(
                        task=user_goal,
                        plan=f"पिछला कोड:\n{current_code}\n\nReviewer की सलाह:\n{review_result.feedback}",
                        attempt=next_attempt,
                        complexity_score=task_complexity,
                    )
                    if current_code_result.success:
                        current_code = self.healer.auto_patch_code(current_code_result.code)
                        attempts = next_attempt
                        continue  # tester + reviewer se dobara guzro
                    else:
                        log += f"❌ Coder ने सुधारने में विफल रहे: {current_code_result.error}\n"
                        break
                else:
                    # Max attempts khatam -- code syntactically/security-wise theek hai,
                    # bas reviewer ki opinion me perfect nahi. Ise fail nahi karte,
                    # best-effort accept karte hain aur warning log karte hain.
                    log += "🚫 Max attempts khatam -- reviewer ki suggestion ke bina hi accept kar rahe hain.\n"
                    self.stats.record(model=current_code_result.model_used or self.model, success=True, attempts=attempts, task_type="coding")
                    self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                                      success=True, attempts=attempts, code=current_code,
                                      error=f"Accepted without review approval: {review_result.feedback}")
                    self.last_goal = user_goal
                    self.last_code = current_code
                    _checkpoint("completed")
                    return OrchestrationResult(success=True, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

            log += f"❌ Tester Failed: {test_result.error_type}\n"
            log += f"   कारण: {test_result.error_message}\n"

            if attempts < self.max_healing_attempts:
                log += f"\n[4/4] Healer: एरर का विश्लेषण कर रहा है और Coder को सुधार का निर्देश दे रहा है...\n"
                healing_result: HealingResult = self.healer.analyze_and_heal(test_result.error_message, user_goal)

                log += f"   पहचाना गया एरर: {healing_result.error_type}\n"
                log += "   Coder को नया प्रॉम्प्ट भेजा जा रहा है...\n"

                next_attempt = attempts + 1
                current_code_result = self.coder.generate_code(
                    task=user_goal,
                    plan=f"पिछला कोड:\n{current_code}\n\nसुधार के निर्देश:\n{healing_result.reflexion_prompt}",
                    attempt=next_attempt,
                    complexity_score=task_complexity,
                )

                if current_code_result.success:
                    current_code = self.healer.auto_patch_code(current_code_result.code)
                    attempts = next_attempt
                else:
                    log += f"❌ Coder ने सुधारने में विफल रहे: {current_code_result.error}\n"
                    break
            else:
                log += f"\n🚫 अधिकतम स्व-उपचार प्रयास ({self.max_healing_attempts}) समाप्त। टास्क विफल।\n"
                break

        self.stats.record(model=current_code_result.model_used or self.model, success=False, attempts=attempts, task_type="coding")
        self.history.log(goal=user_goal, model=current_code_result.model_used or self.model,
                          success=False, attempts=attempts, code=current_code,
                          error="Max healing attempts reached")
        _checkpoint("failed")
        return OrchestrationResult(success=False, final_code=current_code, attempts=attempts, log=log, profile_used=profile_name)

# ==============================================================================
# 3. टेस्टिंग (Testing)
# ==============================================================================

if __name__ == "__main__":
    _orchestrator = SalehaOrchestrator(model="qwen2.5-coder:1.5b", max_healing_attempts=3)
    _res = _orchestrator.execute_task("def add(a, b): return a + b")