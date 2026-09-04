use crate::capability::CapabilityRegistry;
use crate::intent::{Intent, IntentType};
use crate::memory::MemoryStore;
use crate::plan::{PlanEdge, PlanGraph, PlanNode, RiskReport};
use serde_json::json;

pub struct Compiler<'a> {
    registry: &'a CapabilityRegistry,
    memory: &'a MemoryStore,
}

impl<'a> Compiler<'a> {
    pub fn new(registry: &'a CapabilityRegistry, memory: &'a MemoryStore) -> Self {
        Self { registry, memory }
    }

    pub fn compile(&self, intent: &Intent) -> anyhow::Result<PlanGraph> {
        // Memory retrieval
        let _memory_context = self.memory.retrieve(&intent.goal.raw_text);

        // Generate candidates based on intent type
        let nodes = match intent.goal.intent_type {
            IntentType::CodeRepair => self.code_repair_plan(intent),
            IntentType::FileOperation => self.file_operation_plan(intent),
            IntentType::DataAnalysis => self.data_analysis_plan(intent),
            IntentType::SystemMaintenance => self.maintenance_plan(intent),
            IntentType::Generic => self.generic_plan(intent),
        };

        // Filter by allowed/forbidden capabilities
        let nodes: Vec<PlanNode> = nodes
            .into_iter()
            .filter(|n| {
                !intent.forbidden_capabilities.contains(&n.capability)
                    && (intent.allowed_capabilities.is_empty()
                        || intent.allowed_capabilities.contains(&n.capability))
            })
            .collect();

        if nodes.is_empty() {
            return Err(anyhow::anyhow!("No feasible plan found"));
        }

        // Build edges
        let edges: Vec<PlanEdge> = nodes
            .windows(2)
            .map(|w| PlanEdge {
                from: w[0].id.clone(),
                to: w[1].id.clone(),
            })
            .collect();

        let entry_node = nodes.first().map(|n| n.id.clone()).unwrap_or_default();

        // Risk report
        let risk_report = self.build_risk_report(&nodes, intent);

        let plan = PlanGraph {
            id: format!("plan_{}", intent.id),
            intent_id: intent.id.clone(),
            nodes,
            edges,
            entry_node,
            risk_report,
        };

        // Log to memory
        self.memory.record_compilation(intent, &plan);

        Ok(plan)
    }

    fn code_repair_plan(&self, intent: &Intent) -> Vec<PlanNode> {
        vec![
            PlanNode {
                id: "n1".to_string(),
                capability: "run_tests".to_string(),
                input: json!({"phase": "baseline"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
            PlanNode {
                id: "n2".to_string(),
                capability: "read_file".to_string(),
                input: json!({"target": "failing_source"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
            PlanNode {
                id: "n3".to_string(),
                capability: "write_code".to_string(),
                input: json!({"action": "patch"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
            PlanNode {
                id: "n4".to_string(),
                capability: "run_tests".to_string(),
                input: json!({"phase": "verify"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
        ]
    }

    fn file_operation_plan(&self, intent: &Intent) -> Vec<PlanNode> {
        vec![
            PlanNode {
                id: "n1".to_string(),
                capability: "read_file".to_string(),
                input: json!({"action": "scan"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
            PlanNode {
                id: "n2".to_string(),
                capability: "shell".to_string(),
                input: json!({"action": "process", "command": "echo processing"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
        ]
    }

    fn data_analysis_plan(&self, intent: &Intent) -> Vec<PlanNode> {
        vec![
            PlanNode {
                id: "n1".to_string(),
                capability: "read_file".to_string(),
                input: json!({"action": "ingest"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
            PlanNode {
                id: "n2".to_string(),
                capability: "shell".to_string(),
                input: json!({"action": "analyze", "command": "echo analyzing"}),
                timeout_seconds: intent.constraints.time_limit_seconds,
            },
        ]
    }

    fn maintenance_plan(&self, intent: &Intent) -> Vec<PlanNode> {
        vec![PlanNode {
            id: "n1".to_string(),
            capability: "shell".to_string(),
            input: json!({"action": "optimize", "command": "echo optimizing"}),
            timeout_seconds: intent.constraints.time_limit_seconds,
        }]
    }

    fn generic_plan(&self, intent: &Intent) -> Vec<PlanNode> {
        vec![PlanNode {
            id: "n1".to_string(),
            capability: "shell".to_string(),
            input: json!({"action": "execute", "command": "echo executing"}),
            timeout_seconds: intent.constraints.time_limit_seconds,
        }]
    }

    fn build_risk_report(&self, nodes: &[PlanNode], intent: &Intent) -> RiskReport {
        let mut total_risk: f64 = 0.0;
        let mut max_single: f64 = 0.0;
        let mut has_irreversible = false;

        for node in nodes {
            let risk = self.registry.base_risk(&node.capability);
            total_risk += risk;
            max_single = max_single.max(risk);
            if !self.registry.is_reversible(&node.capability) {
                has_irreversible = true;
            }
        }

        let avg_risk = if nodes.is_empty() {
            0.0
        } else {
            total_risk / nodes.len() as f64
        };
        let combined = avg_risk.max(intent.constraints.risk.score());

        RiskReport {
            total_risk: combined,
            max_single_risk: max_single,
            has_irreversible,
            requires_approval: has_irreversible || combined > 0.75,
        }
    }
}
