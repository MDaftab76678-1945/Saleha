"""
Saleha Core: Math Logic & Complexity Estimator (v1.1 - Bilingual & Smart)
उद्देश्य: हिंदी/अंग्रेजी मिश्रित टास्क की जटिलता (Complexity) को गणितीय रूप से मापना,
ताकि एजेंट ओवरलोड न हो और बड़े टास्क को छोटे टुकड़ों (DAG) में बांटा जा सके।
"""

import re
from dataclasses import dataclass

# ==============================================================================
# 1. गणितीय कॉन्फ़िगरेशन (Bilingual Mathematical Configuration)
# ==============================================================================

TASK_WEIGHTS = {
    # 1. High Complexity (Massive scope - तुरंत रोक या तोड़ो)
    r"(पूरे|पूरा|सारे|सभी|सब|entire|whole|all|full).*?(प्रोजेक्ट|कोड|फाइल|फोल्डर|project|code|files|folder|codebase)": 8.0,
    
    # 2. High Complexity (Refactoring everything)
    r"(refactor|rewrite|optimize|debug|दोबारा\s+लिखो|सुधार).*?(पूरे|पूरा|सारे|सभी|सब|entire|whole|all)": 7.0,
    
    # 3. Medium Complexity (Multiple tests or integrations)
    r"(सभी|सारे|सब|all).*?(tests|टेस्ट|जांच|check)": 5.0,
    r"(integrate|जोड़ो|merge).*?(app|application|main|सिस्टम)": 4.0,
    
    # 4. Medium-Low Complexity (Reading multiple files)
    r"(सभी|सारे|सब|all).*?(फाइल|फोल्डर|files|folder)": 3.0,
    
    # 5. Low Complexity (Single file creation)
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
    ".txt": 0.5,  # Added .txt
    ".json": 0.3,
}

# थ्रेशोल्ड (Thresholds)
MAX_SAFE_COMPLEXITY = 5.0  # इससे ऊपर टास्क को तोड़ना (Break down) जरूरी है
CRITICAL_COMPLEXITY = 9.0  # इससे ऊपर तुरंत रुक कर यूजर से पुष्टि लेनी है

# ==============================================================================
# 2. डेटा स्ट्रक्चर्स
# ==============================================================================

@dataclass
class ComplexityResult:
    is_safe_to_run: bool
    complexity_score: float
    estimated_files: int
    recommendation: str  # "EXECUTE", "BREAK_DOWN", "REQUIRES_APPROVAL"

# ==============================================================================
# 3. कोर लॉजिक (Core Logic)
# ==============================================================================

class MathLogicEngine:
    def __init__(self):
        # परफॉर्मेंस के लिए Regex patterns को पहले से कंपाइल कर लें (O(1) lookup time)
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
        estimated_files = 1 # डिफ़ॉल्ट

        # 1. टास्क वेट चेक करें (Hindi + English)
        for pattern, weight in self.compiled_task_weights.items():
            if pattern.search(user_input):
                score += weight
        
        # 2. फाइल एक्सटेंशन का अनुमान लगाएं
        extensions_found = re.findall(r"\.(\w+)", user_input)
        for ext in extensions_found:
            ext_lower = f".{ext.lower()}"
            if ext_lower in FILE_EXTENSION_WEIGHTS:
                score += FILE_EXTENSION_WEIGHTS[ext_lower]
                estimated_files += 1

        # 3. शब्दों की संख्या के आधार पर हल्का वेट (लंबे प्रॉम्प्ट = ज्यादा कॉम्प्लेक्स)
        word_count = len(user_input.split())
        if word_count > 50:
            score += 2.0
        if word_count > 150:
            score += 4.0

        # 4. निर्णय (Decision Making based on Thresholds)
        if score >= CRITICAL_COMPLEXITY:
            recommendation = "REQUIRES_APPROVAL"
            is_safe = False
        elif score >= MAX_SAFE_COMPLEXITY:
            recommendation = "BREAK_DOWN"
            is_safe = True # सुरक्षित है, लेकिन एजेंट को इसे छोटे टुकड़ों में बांटना होगा
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
# 4. टेस्टिंग (Testing)
# ==============================================================================

if __name__ == "__main__":
    engine = MathLogicEngine()
    
    test_cases = [
        "मुझे एक simple Python script बनाकर दो जो hello world print करे।",
        "पूरे प्रोजेक्ट को refactor करो, सभी 50 फाइलों में जाकर database connections को async बनाओ और नए tests लिखो।",
        "इस folder में सभी .txt फाइलें पढ़ो और उनका summary बनाओ।",
        "एक नया React component बनाओ और उसे main app में integrate करो, साथ ही इसके लिए unit tests भी लिख दो।",
        "मेरे सीने में दर्द है, क्या करूँ?" # Safety guard का काम है, लेकिन यहाँ score देखें
    ]

    print("="*70)
    print("🧠 SALEHA MATH LOGIC ENGINE - COMPLEXITY ESTIMATION TEST (v1.1)")
    print("="*70)
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Input: '{test_input}'")
        result = engine.estimate_complexity(test_input)
        print(f"  ➔ Score      : {result.complexity_score}")
        print(f"  ➔ Est. Files : {result.estimated_files}")
        print(f"  ➔ Action     : {result.recommendation}")
        
        if result.recommendation == "BREAK_DOWN":
            print("  💡 Saleha Advice: 'यह टास्क बड़ा है। मैं इसे Planner Agent के जरिए छोटे, manageable चरणों में बांट रहा हूँ।'")
        elif result.recommendation == "REQUIRES_APPROVAL":
            print("  🚨 Saleha Advice: 'यह टास्क बहुत विशाल और जोखिम भरा है। कृपया इसे छोटे हिस्सों में तोड़कर दें।'")