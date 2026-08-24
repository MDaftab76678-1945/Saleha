"""Profile quality audit: kya har profile 'rich' hai ya thin?"""
from saleha.core.agent_profile_loader import profile_registry

print(f"{'profile':34} {'words':>5} {'goals':>5} {'constr':>6} {'tools':>5} {'temp':>4} {'routing':>7}")
thin_profiles = []
for p in sorted(profile_registry.list_profiles(), key=lambda x: x.id):
    words = len(p.body.split()) + len(p.system_prompt.split())
    ng, nc = len(p.goals), len(p.constraints)
    tools = len(p.allowed_tools)
    temp = p.llm_routing.get("temperature", "-")
    routing = bool(p.llm_routing)
    thin = (ng < 3 or nc < 2 or tools == 0 or not routing)
    if thin:
        thin_profiles.append(p.id)
    print(f"{p.id:34} {words:>5} {ng:>5} {nc:>6} {tools:>5} {str(temp):>4} {str(routing):>7}"
          + ("  <-- THIN" if thin else ""))

print()
print("THIN profiles:", len(thin_profiles), "/ 20")
for t in thin_profiles:
    print(" -", t)

# Non-profile md files ka bhi status
import os
skill_files = os.listdir("saleha/skills")
others = [f for f in skill_files if f.endswith(".md") and not f.startswith("agent_")]
print("\nNon-profile reference docs:", others)
