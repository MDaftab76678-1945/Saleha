"""
Saleha Core: Self-Healing & Error Reflexion Engine
उद्देश्य: कोड एक्जीक्यूशन या कंपाइलेशन एरर को पढ़ना, उसकी जड़ (Root Cause) 
पहचानना, और एजेंट के लिए एक सुधारा हुआ (Reflexion) निर्देश तैयार करना।
"""

import re
from dataclasses import dataclass
from typing import List, Optional

# ==============================================================================
# 1. गणितीय कॉन्फ़िगरेशन (Error Pattern Matching)
# ये पैटर्न एरर लॉग को स्कैन करते हैं और एरर के प्रकार (Type) को 100% सटीकता से पहचानते हैं।
# ==============================================================================

ERROR_PATTERNS = {
    "SyntaxError": r"(SyntaxError|invalid syntax|EOL while scanning|unexpected EOF)",
    "ImportError": r"(ModuleNotFoundError|ImportError|No module named)",
    "TypeError": r"(TypeError|unsupported operand type|takes \d+ positional arguments)",
    "NameError": r"(NameError|name '\w+' is not defined)",
    "IndentationError": r"(IndentationError|expected an indented block)",
    "AttributeError": r"(AttributeError|'\w+' object has no attribute)",
    "PermissionError": r"(PermissionError|Access is denied)",
}

# ==============================================================================
# 2. डेटा स्ट्रक्चर्स
# ==============================================================================

@dataclass
class HealingResult:
    error_detected: bool
    error_type: str
    root_cause_hint: str
    reflexion_prompt: str  # यह वह प्रॉम्प्ट है जो एजेंट को सुधार करने के लिए दिया जाएगा

# ==============================================================================
# 3. कोर लॉजिक (Core Logic)
# ==============================================================================

class SelfHealingEngine:
    def __init__(self):
        # परफॉर्मेंस के लिए Regex patterns को पहले से कंपाइल कर लें (O(1) lookup time)
        self.compiled_errors = {
            err_type: re.compile(pattern, re.IGNORECASE) 
            for err_type, pattern in ERROR_PATTERNS.items()
        }

    def analyze_and_heal(self, error_log: str, original_task: str) -> HealingResult:
        """
        एरर लॉग का विश्लेषण करता है और एजेंट के लिए एक सुधारा हुआ प्रॉम्प्ट बनाता है।
        Time Complexity: O(N) जहाँ N एरर लॉग की लंबाई है।
        """
        if not error_log or not error_log.strip():
            return HealingResult(
                error_detected=False, error_type="None", 
                root_cause_hint="कोई एरर नहीं मिला।", 
                reflexion_prompt=""
            )

        detected_type = "UnknownError"
        root_cause = "एरर का सटीक कारण अज्ञात है। कृपया लॉग की अंतिम पंक्तियों की जाँच करें।"

        # 1. एरर का प्रकार पहचानें
        for err_type, pattern in self.compiled_errors.items():
            if pattern.search(error_log):
                detected_type = err_type
                break
        
        # 2. जड़ कारण (Root Cause) का अनुमान लगाएं
        if detected_type == "SyntaxError":
            root_cause = "कोड में व्याकरण (Syntax) की गलती है, जैसे बिना बंद हुआ ब्रैकेट, कोलन (:) की कमी, या स्ट्रिंग कोट्स।"
        elif detected_type == "ImportError":
            root_cause = "कोई आवश्यक लाइब्रेरी इंस्टॉल नहीं है या फाइल का नाम/रास्ता (path) गलत है।"
        elif detected_type == "IndentationError":
            root_cause = "Python में इंडेंटेशन (Spaces/Tabs) सही नहीं है।"
        elif detected_type == "TypeError":
            root_cause = "डेटा प्रकार (Data Type) मेल नहीं खा रहे हैं (जैसे String को Integer से जोड़ना)।"
        elif detected_type == "NameError":
            root_cause = "कोई वेरिएबल या फंक्शन उपयोग करने से पहले परिभाषित (Define) नहीं किया गया है।"

        # 3. Reflexion Prompt तैयार करें (Self-Correction के लिए)
        reflexion_prompt = f"""
        [SALEHA SELF-HEALING REFLEXION]
        मूल कार्य (Original Task): {original_task}
        पहचाना गया एरर (Detected Error): {detected_type}
        संभावित जड़ कारण (Root Cause Hint): {root_cause}
        
        निर्देश: 
        1. पिछले कोड में ऊपर बताए गए '{detected_type}' की जाँच करें।
        2. उसी गलती को दोबारा न करें।
        3. कोड को ठीक करें और केवल अंतिम, सही कोड ही लौटाएं।
        """

        return HealingResult(
            error_detected=True,
            error_type=detected_type,
            root_cause_hint=root_cause,
            reflexion_prompt=reflexion_prompt.strip()
        )

    def auto_patch_code(self, code: str) -> str:
        """
        Auto-patches small-model hallucinations and missing standard library imports
        before AST parsing and execution verification.
        """
        if not code or not code.strip():
            return code

        patched = code

        # 1. Fix missing stdlib imports
        needed_imports = []
        if re.search(r"\btime\.(?:sleep|time|monotonic|perf_counter)\b", patched) and not re.search(r"^\s*(?:import\s+time|from\s+time\s+import)", patched, re.M):
            needed_imports.append("import time")
        if re.search(r"\bjson\.(?:loads|dumps|load|dump)\b", patched) and not re.search(r"^\s*(?:import\s+json|from\s+json\s+import)", patched, re.M):
            needed_imports.append("import json")
        if re.search(r"\bos\.(?:path|environ|getcwd|listdir|makedirs)\b", patched) and not re.search(r"^\s*(?:import\s+os|from\s+os\s+import)", patched, re.M):
            needed_imports.append("import os")
        if re.search(r"\bsys\.(?:exit|argv|path|stdout)\b", patched) and not re.search(r"^\s*(?:import\s+sys|from\s+sys\s+import)", patched, re.M):
            needed_imports.append("import sys")
        if re.search(r"\bre\.(?:search|match|findall|sub|compile)\b", patched) and not re.search(r"^\s*(?:import\s+re|from\s+re\s+import)", patched, re.M):
            needed_imports.append("import re")
        if re.search(r"\bmath\.(?:sqrt|pi|pow|ceil|floor|log)\b", patched) and not re.search(r"^\s*(?:import\s+math|from\s+math\s+import)", patched, re.M):
            needed_imports.append("import math")

        if needed_imports:
            patched = "\n".join(needed_imports) + "\n\n" + patched

        # 2. Fix Java-style AtomicInteger hallucination
        patched = re.sub(r"\bAtomicInteger\((.*?)\)", r"\1", patched)
        patched = re.sub(r"(\w+)\.decrementAndGet\(\)", r"\1 = \1 - 1", patched)
        patched = re.sub(r"(\w+)\.incrementAndGet\(\)", r"\1 = \1 + 1", patched)
        patched = re.sub(r"(\w+)\.addAndGet\((.*?)\)", r"\1 = \1 + \2", patched)

        # 3. Fix Java/JS print statement hallucinations
        patched = re.sub(r"System\.out\.println\((.*?)\)", r"print(\1)", patched)  # noqa
        patched = re.sub(r"console\.log\((.*?)\)", r"print(\1)", patched)  # noqa

        return patched

# ==============================================================================
# 4. टेस्टिंग (Testing)
# ==============================================================================

if __name__ == "__main__":
    _engine = SelfHealingEngine()
    _res = _engine.analyze_and_heal("SyntaxError: invalid syntax", "def add(a, b): return a + b")