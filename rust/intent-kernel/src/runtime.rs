use crate::capability::CapabilityRegistry;
use crate::plan::PlanGraph;
use crate::security::SecurityGateway;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ValidationSeverity {
    Error,
    Warning,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanValidationIssue {
    pub severity: ValidationSeverity,
    pub node_id: Option<String>,
    pub message: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PlanValidationReport {
    pub issues: Vec<PlanValidationIssue>,
}

impl PlanValidationReport {
    pub fn is_valid(&self) -> bool {
        self.error_count() == 0
    }

    pub fn error_count(&self) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == ValidationSeverity::Error)
            .count()
    }

    pub fn warning_count(&self) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == ValidationSeverity::Warning)
            .count()
    }

    fn error(&mut self, node_id: Option<String>, message: impl Into<String>) {
        self.issues.push(PlanValidationIssue {
            severity: ValidationSeverity::Error,
            node_id,
            message: message.into(),
        });
    }

    fn warning(&mut self, node_id: Option<String>, message: impl Into<String>) {
        self.issues.push(PlanValidationIssue {
            severity: ValidationSeverity::Warning,
            node_id,
            message: message.into(),
        });
    }
}

pub struct PlanValidator<'a> {
    registry: &'a CapabilityRegistry,
}

impl<'a> PlanValidator<'a> {
    pub fn new(registry: &'a CapabilityRegistry) -> Self {
        Self { registry }
    }

    pub fn validate(&self, plan: &PlanGraph, forbidden: &[String]) -> PlanValidationReport {
        let mut report = PlanValidationReport::default();

        if plan.nodes.is_empty() {
            report.error(None, "Plan must contain at least one node");
            return report;
        }

        let mut seen = HashSet::new();
        for node in &plan.nodes {
            if node.id.trim().is_empty() {
                report.error(None, "Plan node id cannot be empty");
            } else if !seen.insert(node.id.clone()) {
                report.error(Some(node.id.clone()), "Duplicate plan node id");
            }

            if node.timeout_seconds == 0 {
                report.warning(
                    Some(node.id.clone()),
                    "Node timeout is zero; execution may behave unexpectedly",
                );
            }

            let security = SecurityGateway::check_capability(&node.capability, forbidden);
            if !security.allowed {
                report.error(Some(node.id.clone()), security.reason);
            }

            for issue in self.registry.validate_node(node) {
                report.error(Some(node.id.clone()), issue);
            }
        }

        let node_ids: HashSet<&str> = plan.nodes.iter().map(|node| node.id.as_str()).collect();

        if plan.entry_node.trim().is_empty() {
            report.error(None, "Plan entry_node cannot be empty");
        } else if !node_ids.contains(plan.entry_node.as_str()) {
            report.error(
                None,
                format!("Plan entry_node '{}' does not exist", plan.entry_node),
            );
        }

        for edge in &plan.edges {
            if !node_ids.contains(edge.from.as_str()) {
                report.error(
                    None,
                    format!("Plan edge source '{}' does not exist", edge.from),
                );
            }
            if !node_ids.contains(edge.to.as_str()) {
                report.error(
                    None,
                    format!("Plan edge target '{}' does not exist", edge.to),
                );
            }
        }

        for unreachable in self.unreachable_nodes(plan) {
            report.warning(
                Some(unreachable),
                "Node is not reachable from the plan entry node",
            );
        }

        report
    }

    fn unreachable_nodes(&self, plan: &PlanGraph) -> Vec<String> {
        if plan.entry_node.trim().is_empty() {
            return Vec::new();
        }

        let mut adjacency: HashMap<&str, Vec<&str>> = HashMap::new();
        for edge in &plan.edges {
            adjacency
                .entry(edge.from.as_str())
                .or_default()
                .push(edge.to.as_str());
        }

        let mut visited = HashSet::new();
        let mut stack = vec![plan.entry_node.as_str()];

        while let Some(node_id) = stack.pop() {
            if !visited.insert(node_id) {
                continue;
            }

            if let Some(next) = adjacency.get(node_id) {
                stack.extend(next.iter().copied());
            }
        }

        plan.nodes
            .iter()
            .filter(|node| !visited.contains(node.id.as_str()))
            .map(|node| node.id.clone())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plan::{PlanEdge, PlanNode, RiskReport};
    use serde_json::json;

    fn single_node_plan(capability: &str, input: serde_json::Value) -> PlanGraph {
        PlanGraph {
            id: "plan_test".to_string(),
            intent_id: "intent_test".to_string(),
            nodes: vec![PlanNode {
                id: "n1".to_string(),
                capability: capability.to_string(),
                input,
                timeout_seconds: 30,
            }],
            edges: vec![],
            entry_node: "n1".to_string(),
            risk_report: RiskReport::default(),
        }
    }

    #[test]
    fn rejects_unknown_capabilities() {
        let registry = CapabilityRegistry::new();
        let validator = PlanValidator::new(&registry);
        let plan = single_node_plan("teleport", json!({}));

        let report = validator.validate(&plan, &[]);

        assert!(!report.is_valid());
        assert!(report
            .issues
            .iter()
            .any(|issue| issue.message.contains("Unknown capability")));
    }

    #[test]
    fn rejects_missing_required_inputs() {
        let registry = CapabilityRegistry::new();
        let validator = PlanValidator::new(&registry);
        let plan = single_node_plan("read_file", json!({}));

        let report = validator.validate(&plan, &[]);

        assert!(!report.is_valid());
        assert!(report
            .issues
            .iter()
            .any(|issue| issue.message.contains("requires input 'path'")));
    }

    #[test]
    fn accepts_valid_write_file_plan() {
        let registry = CapabilityRegistry::new();
        let validator = PlanValidator::new(&registry);
        let plan = single_node_plan(
            "write_file",
            json!({"path": "demo_workspace/config.txt", "content": "ok"}),
        );

        let report = validator.validate(&plan, &[]);

        assert!(report.is_valid(), "{:?}", report.issues);
    }

    #[test]
    fn reports_unreachable_nodes() {
        let registry = CapabilityRegistry::new();
        let validator = PlanValidator::new(&registry);
        let mut plan = single_node_plan("shell", json!({"command": "echo ok"}));
        plan.nodes.push(PlanNode {
            id: "n2".to_string(),
            capability: "run_tests".to_string(),
            input: json!({"phase": "verify"}),
            timeout_seconds: 30,
        });
        plan.edges = vec![PlanEdge {
            from: "missing".to_string(),
            to: "n2".to_string(),
        }];

        let report = validator.validate(&plan, &[]);

        assert!(report.warning_count() > 0);
        assert!(report
            .issues
            .iter()
            .any(|issue| issue.message.contains("not reachable")));
    }
}
