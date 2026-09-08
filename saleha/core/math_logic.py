"""
Saleha Core: Math Logic & Complexity Estimator (v1.1 - Bilingual & Smart)

Purpose: measure the complexity of a mixed Hindi/English task numerically, so
the agent is not overloaded and large tasks are split into smaller pieces (a
DAG).

Note: the TASK_WEIGHTS patterns below deliberately contain Hindi keywords.
The user writes goals in Hindi or a Hindi/English mix, and these patterns are
matched against that raw input -- they are data the estimator reads, not
prose. Everything else in this file is English.
"""

import re
from dataclasses import dataclass

# ==============================================================================
# 1. Bilingual mathematical configuration
# ==============================================================================

TASK_WEIGHTS = {
    # 1. High complexity (massive scope -- stop or break down immediately)
    r"(पूरे|पूरा|सारे|सभी|सब|entire|whole|all|full).*?(प्रोजेक्ट|कोड|फाइल|फोल्डर|project|code|files|folder|codebase)": 8.0,

    # 2. High complexity (refactoring everything)
    r"(refactor|rewrite|optimize|debug|दोबारा\s+लिखो|सुधार).*?(पूरे|पूरा|सारे|सभी|सब|entire|whole|all)": 7.0,

    # 3. Medium complexity (multiple tests or integrations)
    r"(सभी|सारे|सब|all).*?(tests|टेस्ट|जांच|check)": 5.0,
    r"(integrate|जोड़ो|merge).*?(app|application|main|सिस्टम)": 4.0,

    # 4. Medium-low complexity (reading multiple files)
    r"(सभी|सारे|सब|all).*?(फाइल|फोल्डर|files|folder)": 3.0,

    # 5. Low complexity (single file creation)
    r"(create|build|write|generate|बनाओ|लिखो).*?(एक|a|an|one|single).*?(file|script|function|फाइल|स्क्रिप्ट|component)": 2.0,

    # 6. Base testing keyword
    r"\b(tests|टेस्ट|जांच|check|verify)\b": 2.0,
}

FILE_EXTENSION_WEIGHTS = {
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
MAX_SAFE_COMPLEXITY = 5.0  # above this, the task must be broken down
CRITICAL_COMPLEXITY = 9.0  # above this, stop and confirm with the user

# ==============================================================================
# 2. Data structures
# ==============================================================================

@dataclass
class ComplexityResult:
    is_safe_to_run: bool
    complexity_score: float
    estimated_files: int
    recommendation: str  # "EXECUTE", "BREAK_DOWN", "REQUIRES_APPROVAL"

# ==============================================================================
# 3. Core Logic
# ==============================================================================

class MathLogicEngine:
    def __init__(self):
        # Pre-compile the regex patterns for performance (O(1) lookup time).
        self.compiled_task_weights = {
            re.compile(pattern, re.IGNORECASE): weight
            for pattern, weight in TASK_WEIGHTS.items()
        }

    def estimate_complexity(self, user_input: str) -> ComplexityResult:
        if not user_input or not user_input.strip():
            return ComplexityResult(
                is_safe_to_run=True, complexity_score=0.0,
                estimated_files=1, recommendation="EXECUTE"
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

        return ComplexityResult(
            is_safe_to_run=is_safe,
            complexity_score=round(score, 2),
            estimated_files=estimated_files,
            recommendation=recommendation
        )

# ==============================================================================
# 4. Testing
# ==============================================================================

if __name__ == "__main__":
    engine = MathLogicEngine()

    # Inputs stay in Hindi/mixed on purpose: this is what the estimator sees
    # in production, and the patterns above are what match it.
    test_cases = [
        "मुझे एक simple Python script बनाकर दो जो hello world print करे।",
        "पूरे प्रोजेक्ट को refactor करो, सभी 50 फाइलों में जाकर database connections को async बनाओ और नए tests लिखो।",
        "इस folder में सभी .txt फाइलें पढ़ो और उनका summary बनाओ।",
        "एक नया React component बनाओ और उसे main app में integrate करो, साथ ही इसके लिए unit tests भी लिख दो।",
        "मेरे सीने में दर्द है, क्या करूँ?",  # safety_guard's job; here we only look at the score
    ]

    print("="*70)
    print("SALEHA MATH LOGIC ENGINE - COMPLEXITY ESTIMATION TEST (v1.1)")
    print("="*70)

    for i, test_input in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Input: '{test_input}'")
        result = engine.estimate_complexity(test_input)
        print(f"  -> Score      : {result.complexity_score}")
        print(f"  -> Est. Files : {result.estimated_files}")
        print(f"  -> Action     : {result.recommendation}")

        if result.recommendation == "BREAK_DOWN":
            print("  Advice: this task is large; splitting it into smaller, "
                  "manageable steps via the Planner Agent.")
        elif result.recommendation == "REQUIRES_APPROVAL":
            print("  Advice: this task is very large and risky; please break "
                  "it into smaller pieces.")
