use crate::plan::PlanNode;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Capability {
    pub name: String,
    pub description: String,
    pub reversible: bool,
    pub base_risk: f64,
    pub cost: CostLevel,
    pub preconditions: Vec<String>,
    pub required_inputs: Vec<String>,
    pub effects: Vec<String>,
    pub required_proof: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum CostLevel {
    Low,
    Medium,
    High,
}

pub struct CapabilityRegistry {
    capabilities: HashMap<String, Capability>,
}

impl Default for CapabilityRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl CapabilityRegistry {
    pub fn new() -> Self {
        let mut registry = Self {
            capabilities: HashMap::new(),
        };
        registry.register_defaults();
        registry
    }

    fn register_defaults(&mut self) {
        let defaults = vec![
            Capability {
                name: "read_file".to_string(),
                description: "Read a file".to_string(),
                reversible: true,
                base_risk: 0.1,
                cost: CostLevel::Low,
                preconditions: vec!["file_exists".to_string()],
                required_inputs: vec!["path".to_string()],
                effects: vec!["file_read".to_string()],
                required_proof: vec!["execution_proof".to_string()],
            },
            Capability {
                name: "write_file".to_string(),
                description: "Write content to a file".to_string(),
                reversible: true,
                base_risk: 0.35,
                cost: CostLevel::Low,
                preconditions: vec!["file_writable".to_string()],
                required_inputs: vec!["path".to_string(), "content".to_string()],
                effects: vec!["file_modified".to_string()],
                required_proof: vec!["file_diff".to_string(), "execution_proof".to_string()],
            },
            Capability {
                name: "create_file".to_string(),
                description: "Create a new file".to_string(),
                reversible: true,
                base_risk: 0.25,
                cost: CostLevel::Low,
                preconditions: vec!["parent_directory_writable".to_string()],
                required_inputs: vec!["path".to_string(), "content".to_string()],
                effects: vec!["file_created".to_string()],
                required_proof: vec!["execution_proof".to_string()],
            },
            Capability {
                name: "write_code".to_string(),
                description: "Modify source code".to_string(),
                reversible: true,
                base_risk: 0.45,
                cost: CostLevel::Medium,
                preconditions: vec!["file_writable".to_string()],
                required_inputs: vec!["path".to_string(), "content".to_string()],
                effects: vec!["file_modified".to_string()],
                required_proof: vec!["file_diff".to_string(), "test_result".to_string()],
            },
            Capability {
                name: "run_tests".to_string(),
                description: "Run test suite".to_string(),
                reversible: true,
                base_risk: 0.2,
                cost: CostLevel::Medium,
                preconditions: vec!["code_compiles".to_string()],
                required_inputs: vec![],
                effects: vec!["test_result".to_string()],
                required_proof: vec!["test_result".to_string()],
            },
            Capability {
                name: "shell".to_string(),
                description: "Execute shell command".to_string(),
                reversible: false,
                base_risk: 0.5,
                cost: CostLevel::Low,
                preconditions: vec!["command_safe".to_string()],
                required_inputs: vec!["command".to_string()],
                effects: vec!["command_executed".to_string()],
                required_proof: vec!["execution_proof".to_string()],
            },
            Capability {
                name: "delete_files".to_string(),
                description: "Delete files".to_string(),
                reversible: false,
                base_risk: 0.9,
                cost: CostLevel::Low,
                preconditions: vec!["explicit_approval".to_string()],
                required_inputs: vec!["path".to_string()],
                effects: vec!["file_deleted".to_string()],
                required_proof: vec!["approval_proof".to_string()],
            },
        ];

        for cap in defaults {
            self.capabilities.insert(cap.name.clone(), cap);
        }
    }

    pub fn get(&self, name: &str) -> Option<&Capability> {
        self.capabilities.get(name)
    }

    pub fn contains(&self, name: &str) -> bool {
        self.capabilities.contains_key(name)
    }

    pub fn is_reversible(&self, name: &str) -> bool {
        self.capabilities
            .get(name)
            .map(|c| c.reversible)
            .unwrap_or(false)
    }

    pub fn base_risk(&self, name: &str) -> f64 {
        self.capabilities
            .get(name)
            .map(|c| c.base_risk)
            .unwrap_or(1.0)
    }

    pub fn validate_node(&self, node: &PlanNode) -> Vec<String> {
        let Some(capability) = self.get(&node.capability) else {
            return vec![format!("Unknown capability '{}'", node.capability)];
        };

        capability
            .required_inputs
            .iter()
            .filter(|key| Self::missing_required_input(node, key))
            .map(|key| format!("Capability '{}' requires input '{}'", node.capability, key))
            .collect()
    }

    pub fn all_names(&self) -> Vec<String> {
        let mut names: Vec<String> = self.capabilities.keys().cloned().collect();
        names.sort();
        names
    }

    fn missing_required_input(node: &PlanNode, key: &str) -> bool {
        match node.input.get(key) {
            None => true,
            Some(value) if value.is_null() => true,
            Some(value) => value.as_str().is_some_and(|s| s.trim().is_empty()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn registry_contains_executor_capabilities() {
        let registry = CapabilityRegistry::new();

        for name in [
            "shell",
            "read_file",
            "write_code",
            "write_file",
            "create_file",
            "run_tests",
        ] {
            assert!(registry.contains(name), "missing capability: {name}");
        }
    }

    #[test]
    fn validate_node_reports_missing_required_inputs() {
        let registry = CapabilityRegistry::new();
        let node = PlanNode {
            id: "n1".to_string(),
            capability: "write_file".to_string(),
            input: json!({"path": "demo.txt"}),
            timeout_seconds: 30,
        };

        let issues = registry.validate_node(&node);

        assert_eq!(issues.len(), 1);
        assert!(issues[0].contains("content"));
    }
}
