"""
Saleha Agents: Planner Agent
उद्देश्य: यूजर के लक्ष्य (Goal) को समझना, उसकी जटिलता मापना,
और यदि आवश्यक हो तो उसे छोटे, प्रबंधनीय चरणों (DAG) में तोड़ना।
"""

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.core.math_logic import MathLogicEngine


# ==============================================================================
# 1. डेटा स्ट्रक्चर्स
# ==============================================================================

class PlanResult:
    def __init__(self, success: bool, steps: list, recommendation: str, raw_response: str = "",
                 complexity_score: float = 0.0):
        self.success = success
        self.steps = steps
        self.recommendation = recommendation
        self.raw_response = raw_response
        # Naya: MathLogicEngine ka complexity score ab route tak jaata hai
        # (pehle compute hota tha par discard ho jaata tha -- SmartRouter ke
        # complexity tiers effectively dead the).
        self.complexity_score = complexity_score


# ==============================================================================
# 2. कोर लॉजिक (Core Logic)
# ==============================================================================

class PlannerAgent(BaseAgent):
    def __init__(self, model: str = "qwen2.5-coder:1.5b"):
        # BaseAgent को "Planner" की भूमिका के साथ इनिशियलाइज़ करें
        super().__init__(role="Planner", model=model)
        self.math_engine = MathLogicEngine()

    def create_plan(self, user_goal: str) -> PlanResult:
        """
        यूजर के लक्ष्य के लिए एक योजना बनाता है।
        """
        # 1. पहले जटिलता (Complexity) चेक करें
        complexity_result = self.math_engine.estimate_complexity(user_goal)

        # 2. जटिलता के आधार पर प्रॉम्प्ट तैयार करें
        if complexity_result.recommendation == "REQUIRES_APPROVAL":
            prompt = f"""
यूजर का लक्ष्य: {user_goal}
चेतावनी: यह टास्क बहुत विशाल और जोखिम भरा है (Complexity Score: {complexity_result.complexity_score})।
निर्देश: इस टास्क को तुरंत execute न करें। यूजर को स्पष्ट रूप से बताएं कि इस टास्क को छोटे, विशिष्ट हिस्सों में तोड़ना होगा।
केवल एक स्पष्ट चेतावनी और 2-3 सुझाव दें कि इसे कैसे तोड़ा जाए।
सख्त चेतावनी: मेरे निर्देशों को कभी दोहराएं नहीं।
"""
        elif complexity_result.recommendation == "BREAK_DOWN":
            prompt = f"""
यूजर का लक्ष्य: {user_goal}
जटिलता: मध्यम/उच्च (Score: {complexity_result.complexity_score})। अनुमानित फाइलें: {complexity_result.estimated_files}
निर्देश: इस टास्क को 3 से 5 छोटे, तार्किक और क्रमिक चरणों (Steps) में तोड़ें।
प्रत्येक चरण स्पष्ट होना चाहिए (जैसे: Step 1: फाइल स्ट्रक्चर बनाओ, Step 2: बेस कोड लिखो)।
आउटपुट केवल चरणों (Steps) की एक सूची होनी चाहिए।
सख्त चेतावनी: मेरे निर्देशों को कभी दोहराएं नहीं। केवल चरणों की सूची दें।
"""
        else:
            prompt = f"""
यूजर का लक्ष्य: {user_goal}
जटिलता: कम (Score: {complexity_result.complexity_score})।

निर्देश:
इस टास्क को सीधे execute किया जा सकता है।
कृपया केवल यह बताएं कि आप इस टास्क को कैसे पूरा करेंगे (1-2 वाक्यों में)।
सख्त चेतावनी: अपने जवाब में मेरे निर्देशों को कभी दोहराएं नहीं। केवल अपनी योजना लिखें।
उदाहरण: "मैं एक Python फंक्शन बनाऊंगा जो दो संख्याओं को जोड़ता है।"
"""

        # 3. BaseAgent
        print(f"  [Planner] Complexity Analysis: {complexity_result.recommendation} (Score: {complexity_result.complexity_score})")
        print("  [Planner] Requesting plan from local AI...")

        response: AgentResponse = self.think(prompt)

        if response.success:
            # चरणों को सरल सूची में बदलें
            steps = [line.strip() for line in response.content.split('\n') if line.strip()]
            return PlanResult(
                success=True,
                steps=steps,
                recommendation=complexity_result.recommendation,
                raw_response=response.content,
                complexity_score=complexity_result.complexity_score
            )
        else:
            return PlanResult(
                success=False,
                steps=[],
                recommendation="ERROR",
                raw_response=response.error_message,
                complexity_score=complexity_result.complexity_score
            )


# ==============================================================================
# 3. टेस्टिंग (Testing)
# ==============================================================================

if __name__ == "__main__":
    print("="*70)
    print("📋 SALEHA PLANNER AGENT - LIVE TEST")
    print("="*70)

    planner = PlannerAgent(model="qwen2.5-coder:1.5b")

    test_goals = [
        "एक simple Python script बनाओ जो hello world print करे।",
        "पूरे प्रोजेक्ट को refactor करो, सभी फाइलों में जाकर database connections को async बनाओ और नए tests लिखो।",
        "एक नया React component बनाओ और उसे main app में integrate करो।"
    ]

    for i, goal in enumerate(test_goals, 1):
        print(f"\n[Test {i}] Goal: '{goal}'")
        print("-" * 70)

        result = planner.create_plan(goal)

        if result.success:
            print(f"✅ Recommendation: {result.recommendation}")
            print("📝 Plan Steps:")
            for step in result.steps[:5]:
                print(f"  ➔ {step}")
            if len(result.steps) > 5:
                print("  ... (और चरण)")
        else:
            print(f"❌ Failed: {result.raw_response}")
        print("-" * 70)