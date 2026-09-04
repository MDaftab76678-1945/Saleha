from general_reasoning_engine import GeneralReasoningEngine, ReasoningStrategy

# Inside JarvisBackendWorker class
self.reasoning_engine = GeneralReasoningEngine()

# Register domain knowledge
self.reasoning_engine.causal.add_causal_link("build error", "test failure", 0.90)
self.reasoning_engine.causal.add_causal_link("test failure", "deployment block", 0.85)

# Use in query processing
chain = self.reasoning_engine.get_best_reasoning(
    user_query,
    context={"facts": extracted_facts, "observations": past_events}
)

# Inject reasoning context into LLM prompt
reasoning_context = f"\n[REASONING CHAIN]: {chain.final_conclusion}"
