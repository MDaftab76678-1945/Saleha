"""
Saleha Core: Math Logic & Complexity Estimator (v1.2 - Bilingual & Smart)

Purpose: measure the complexity of a mixed Hindi/English task numerically, so
the agent is not overloaded and large tasks are split into smaller pieces (a
DAG).

Note: the TASK_WEIGHTS patterns below deliberately contain Hindi keywords.
The user writes goals in Hindi or a Hindi/English mix, and these patterns are
matched against that raw input -- they are data the estimator reads, not
prose. Everything else in this file is English.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Pattern

if TYPE_CHECKING:
    from saleha.core.dag_engine import TaskDAG

# ==============================================================================
# 1. Bilingual mathematical configuration
# ==============================================================================

# Each pattern carries three scripts for the same intent: English, Devanagari
# Hindi, and romanized Hinglish (Hindi typed in Latin letters, e.g. "poore
# project ko dobara likho"). Romanized input is what users actually type most
# of the time -- a Devanagari-only pattern scored it 0.0, so a full-codebase
# refactor was read as a trivial task. Spelling varies freely when Hindi is
# romanized ("poora"/"pura", "saare"/"sare", "likho"/"likhho"), so the
# alternations below deliberately admit common variants rather than one
# canonical spelling.
TASK_WEIGHTS: Dict[str, float] = {
    # 1. High complexity (massive scope -- stop or break down immediately)
    r"(पूरे|पूरा|सारे|सभी|सब|p[uo]{1,2}r[ae]|s[aā]{1,2}r[ae]|sabhi|sab|entire|whole|all|full)\s.*?(प्रोजेक्ट|कोड|फाइल|फोल्डर|project|code|files?|folder|codebase|repo)": 8.0,

    # 2. High complexity (refactoring everything)
    r"(refactor|rewrite|optimize|debug|दोबारा\s+लिखो|सुधार|dobara\s+likh|sudhar).*?(पूरे|पूरा|सारे|सभी|सब|p[uo]{1,2}r[ae]|s[aā]{1,2}r[ae]|sabhi|sab|entire|whole|all)": 7.0,
    r"(पूरे|पूरा|सारे|सभी|सब|p[uo]{1,2}r[ae]|s[aā]{1,2}r[ae]|sabhi|sab)\s.*?(दोबारा\s+लिखो|सुधार|dobara\s+likh|refactor|rewrite|optimi[sz]e)": 7.0,

    # 3. High complexity (full-stack or end-to-end applications)
    r"(frontend\s+and\s+backend|full\s*stack|फुल\s*स्टैक|ful{1,2}\s*stack|end\s*to\s*end|एंड\s*टू\s*एंड)": 6.0,

    # 4. Medium-high complexity (distributed systems, microservices, pipeline engines)
    r"\b(microservices?|distributed\s+system|cluster\s+node|pipeline\s+engine|माइक्रोसर्विस|डिस्ट्रिब्यूटेड|microservis|distributed)\b": 4.5,

    # 5. Medium complexity (database migration or schema design)
    r"\b((database|schema|db)\s+migration|माइग्रेशन|डेटाबेस\s+स्कीमा|migration)\b": 4.0,

    # 6. Medium complexity (security audits & penetration testing)
    r"\b(security\s+audit|vulnerability\s+scan|penetration\s+test|auth\s+system|सुरक्षा\s+ऑडिट|suraksha\s+audit)\b": 4.0,

    # 7. Medium complexity (multiple tests or integrations)
    r"(सभी|सारे|सब|s[aā]{1,2}r[ae]|sabhi|sab|all)\s.*?(tests?|टेस्ट|जांच|test|jaanch|janch|check)": 5.0,
    r"(integrate|जोड़ो|merge|jodo|jod\s+do)\s.*?(app|application|main|सिस्टम|system)": 4.0,

    # 8. Medium-low complexity (reading multiple files)
    r"(सभी|सारे|सब|s[aā]{1,2}r[ae]|sabhi|sab|all)\s.*?(फाइल|फोल्डर|files?|folder|file)": 3.0,

    # 9. Low complexity (single file creation). Hindi puts the verb last
    # ("ek file banao"), English puts it first ("create a file"), so both
    # orderings are matched.
    r"(create|build|write|generate|बनाओ|लिखो|banao|likho)\s.*?(एक|a|an|one|single|ek)\s.*?(file|script|function|फाइल|स्क्रिप्ट|component)": 2.0,
    r"(एक|one|single|ek)\s.*?(file|script|function|फाइल|स्क्रिप्ट|component)\s.*?(बनाओ|लिखो|banao|likho|bana\s+do)": 2.0,

    # 10. Base testing keyword
    r"\b(tests?|टेस्ट|जांच|jaanch|janch|check|verify)\b": 2.0,
}

FILE_EXTENSION_WEIGHTS: Dict[str, float] = {
    ".py": 1.0,
    ".js": 1.0,
    ".cpp": 2.0,
    ".rs": 2.0,
    ".yaml": 0.5,
    ".md": 0.2,
    ".txt": 0.5,
    ".json": 0.3,
}

# Thresholds
MAX_SAFE_COMPLEXITY: float = 5.0  # above this, the task must be broken down
CRITICAL_COMPLEXITY: float = 9.0  # above this, stop and confirm with the user

# ==============================================================================
# 2. Data structures
# ==============================================================================

@dataclass
class ComplexityResult:
    is_safe_to_run: bool
    complexity_score: float
    estimated_files: int
    recommendation: str  # "EXECUTE", "BREAK_DOWN", "REQUIRES_APPROVAL"
    suggested_stages: List[str] = field(default_factory=list)

# ==============================================================================
# 3. Core Logic
# ==============================================================================

class MathLogicEngine:
    def __init__(self) -> None:
        # Pre-compile the regex patterns for performance (O(1) lookup time).
        self.compiled_task_weights: Dict[Pattern[str], float] = {
            re.compile(pattern, re.IGNORECASE): weight
            for pattern, weight in TASK_WEIGHTS.items()
        }

    def estimate_complexity(self, user_input: str) -> ComplexityResult:
        if not user_input or not user_input.strip():
            return ComplexityResult(
                is_safe_to_run=True,
                complexity_score=0.0,
                estimated_files=1,
                recommendation="EXECUTE",
                suggested_stages=["core_implementation"],
            )

        score = 0.0
        estimated_files = 1  # default

        # 1. Check task weights (Hindi + English).
        for pattern, weight in self.compiled_task_weights.items():
            if pattern.search(user_input):
                score += weight

        # 2. Estimate from file extensions mentioned.
        extensions_found = re.findall(r"\.(\w+)", user_input)
        for ext in extensions_found:
            ext_lower = f".{ext.lower()}"
            if ext_lower in FILE_EXTENSION_WEIGHTS:
                score += FILE_EXTENSION_WEIGHTS[ext_lower]
                estimated_files += 1

        # 3. Light weight from word count (longer prompt = more complex).
        word_count = len(user_input.split())
        if word_count > 50:
            score += 2.0
        if word_count > 150:
            score += 4.0

        # 4. Decision based on thresholds.
        if score >= CRITICAL_COMPLEXITY:
            recommendation = "REQUIRES_APPROVAL"
            is_safe = False
        elif score >= MAX_SAFE_COMPLEXITY:
            recommendation = "BREAK_DOWN"
            is_safe = True  # safe, but the agent must split it into smaller pieces
        else:
            recommendation = "EXECUTE"
            is_safe = True

        # 5. Extract suggested architectural stages
        suggested_stages: List[str] = []
        user_lower = user_input.lower()
        if re.search(r"frontend\s+and\s+backend|full\s*stack|फुल\s*स्टैक|end\s*to\s*end", user_lower):
            suggested_stages.append("full_stack")
        if re.search(r"microservice|distributed|cluster|माइक्रोसर्विस|डिस्ट्रिब्यूटेड", user_lower):
            suggested_stages.append("distributed_architecture")
        if re.search(r"migration|schema|database|माइग्रेशन|डेटाबेस", user_lower):
            suggested_stages.append("database_migration")
        if re.search(r"security|vulnerability|audit|सुरक्षा", user_lower):
            suggested_stages.append("security_hardening")
        if re.search(r"tests|टेस्ट|verify|जांच", user_lower):
            suggested_stages.append("test_automation")

        if not suggested_stages:
            suggested_stages = ["core_implementation", "test_automation"]

        return ComplexityResult(
            is_safe_to_run=is_safe,
            complexity_score=round(score, 2),
            estimated_files=estimated_files,
            recommendation=recommendation,
            suggested_stages=suggested_stages,
        )

    def decompose_to_dag(
        self,
        user_input: str,
        goal: Optional[str] = None,
        model: str = "auto",
    ) -> TaskDAG:
        """
        Constructs a customized, topologically ordered TaskDAG based on the detected
        complexity components in the user input.
        """
        from saleha.core.dag_engine import TaskDAG, TaskNode

        effective_goal = goal or user_input.strip()[:120]
        dag = TaskDAG(goal=effective_goal, model=model)

        res = self.estimate_complexity(user_input)
        stages = set(res.suggested_stages)

        # Always start with requirements / specification
        dag.add_task(TaskNode(
            id="task_spec",
            title="Requirements & Interface Specifications",
            role_profile="agent_product_manager",
            prompt=f"Define specifications, interfaces, and acceptance criteria for: {effective_goal}",
        ))

        # Architecture design
        dag.add_task(TaskNode(
            id="task_arch",
            title="System Architecture & Data Contracts",
            role_profile="agent_software_designer",
            prompt=f"Design modular architecture, schemas, and contract interfaces for: {effective_goal}",
            depends_on=["task_spec"],
        ))

        # Determine implementation nodes
        impl_deps: List[str] = ["task_arch"]
        core_deps: List[str] = []

        if "database_migration" in stages:
            dag.add_task(TaskNode(
                id="task_db",
                title="Database Schema & Persistence Layer",
                role_profile="agent_software_designer",
                prompt=f"Implement database models, migration scripts, and persistence layer for: {effective_goal}",
                depends_on=["task_arch"],
            ))
            impl_deps.append("task_db")

        if "full_stack" in stages:
            dag.add_task(TaskNode(
                id="task_backend",
                title="Backend APIs & Domain Services",
                role_profile="agent_sde",
                prompt=f"Implement backend services, routing, and business logic for: {effective_goal}",
                depends_on=list(impl_deps),
            ))
            dag.add_task(TaskNode(
                id="task_frontend",
                title="Frontend UI & Client Components",
                role_profile="agent_sde",
                prompt=f"Implement responsive client UI components for: {effective_goal}",
                depends_on=["task_arch"],
            ))
            core_deps = ["task_backend", "task_frontend"]
        elif "distributed_architecture" in stages:
            dag.add_task(TaskNode(
                id="task_core",
                title="Distributed Protocol & Node Cluster Engine",
                role_profile="agent_sde",
                prompt=f"Implement distributed protocols, pipeline stages, and concurrent engine for: {effective_goal}",
                depends_on=list(impl_deps),
            ))
            core_deps = ["task_core"]
        else:
            dag.add_task(TaskNode(
                id="task_core",
                title="Core Module Implementation",
                role_profile="agent_sde",
                prompt=f"Implement core logic, algorithms, and modules for: {effective_goal}",
                depends_on=list(impl_deps),
            ))
            core_deps = ["task_core"]

        # Security audit stage
        dag.add_task(TaskNode(
            id="task_security",
            title="Security & Vulnerability Audit",
            role_profile="agent_security_engineer",
            prompt=f"Audit codebase for injection, authorization, and resource limit vulnerabilities for: {effective_goal}",
            depends_on=list(core_deps),
        ))

        # QA & Test Automation stage
        dag.add_task(TaskNode(
            id="task_qa",
            title="Automated Test Suite & Verification",
            role_profile="agent_test_automation_engineer",
            prompt=f"Author comprehensive pytest test suite validating all interfaces for: {effective_goal}",
            depends_on=list(core_deps),
        ))

        return dag

