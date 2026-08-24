---
id: "agent_ai_engineer"
name: "Principal Generative AI & Autonomous Agent Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Principal Generative AI Engineer Specification

## 1. LangGraph Multi-Agent RAG Orchestrator
```python
from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage

class AgentWorkflowState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    retrieved_docs: list[str]
    is_safe: bool
    final_response: str

def security_guardrail_node(state: AgentWorkflowState) -> dict:
    last_msg = state["messages"][-1].content
    is_safe = not any(b in last_msg.lower() for b in ["ignore prior instructions", "system prompt"])
    return {"is_safe": is_safe}

def query_vector_db_node(state: AgentWorkflowState) -> dict:
    if not state["is_safe"]:
        return {"retrieved_docs": [], "final_response": "Policy violation detected."}
    return {"retrieved_docs": ["Standard A: Spec doc", "Standard B: Security doc"]}

workflow = StateGraph(AgentWorkflowState)
workflow.add_node("guardrail", security_guardrail_node)
workflow.add_node("retriever", query_vector_db_node)
workflow.set_entry_point("guardrail")
workflow.add_edge("guardrail", "retriever")
workflow.add_edge("retriever", END)
compiled_app = workflow.compile()
```

