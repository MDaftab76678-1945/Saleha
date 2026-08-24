---
id: "agent_business_analyst"
name: "Senior Business Systems Analyst"
type: "agent_profile"
version: "2.0.0"
---

# Senior Business Systems Analyst Specification

## 1. BPMN 2.0 Process Workflow
```text
[Customer Initiates Order]
            │
            ▼
[Is Inventory Available in DB?] ──No──► [Trigger Out-of-Stock Alert]
            │ Yes
            ▼
[Execute Card Authorization via Gateway]
            │
      ┌─────┴─────┐
   Success      Failure
      │           │
      ▼           ▼
[Emit OrderPlacedEvent]   [Trigger Retry / Send Failure Email]
```

