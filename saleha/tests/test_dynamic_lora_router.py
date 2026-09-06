import pytest

from saleha.core.dynamic_lora_router import MicroAdapterSpec, LoRARoutingDecision, DynamicLoRARouter


def test_route_and_switch():
    router = DynamicLoRARouter()
    
    # Test case 1: Prompt contains "react"
    task_prompt_1 = "Create a simple React component for displaying user information."
    decision_1 = router.route_and_switch(task_prompt_1)
    assert decision_1.detected_domain == "frontend", f"Expected 'frontend' but got {decision_1.detected_domain}"
    
    # Test case 2: Prompt contains "security"
    task_prompt_2 = "Implement a secure login system using JWT."
    decision_2 = router.route_and_switch(task_prompt_2)
    assert decision_2.detected_domain == "security", f"Expected 'security' but got {decision_2.detected_domain}"
    
    # Test case 3: Prompt contains "postgres"
    task_prompt_3 = "Fetch data from a PostgreSQL database."
    decision_3 = router.route_and_switch(task_prompt_3)
    assert decision_3.detected_domain == "database", f"Expected 'database' but got {decision_3.detected_domain}"
    
    # Test case 4: Prompt contains "algorithm"
    task_prompt_4 = "Implement a dynamic programming algorithm for solving the knapsack problem."
    decision_4 = router.route_and_switch(task_prompt_4)
    assert decision_4.detected_domain == "algorithms", f"Expected 'algorithms' but got {decision_4.detected_domain}"
    
    # Test case 5: Prompt contains "fastapi"
    task_prompt_5 = "Create a RESTful API using FastAPI."
    decision_5 = router.route_and_switch(task_prompt_5)
    assert decision_5.detected_domain == "backend", f"Expected 'backend' but got {decision_5.detected_domain}"
    
    # Test case 6: General prompt
    task_prompt_general = "Write a general polyglot coding and documentation example."
    decision_general = router.route_and_switch(task_prompt_general)
    assert decision_general.detected_domain == "general", f"Expected 'general' but got {decision_5.detected_domain}"
    
    print("All test cases passed!")