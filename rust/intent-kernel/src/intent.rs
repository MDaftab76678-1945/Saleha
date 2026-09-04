use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Intent {
    pub id: String,
    pub goal: Goal,
    pub constraints: Constraints,
    pub allowed_capabilities: Vec<String>,
    pub forbidden_capabilities: Vec<String>,
    pub rollback_policy: RollbackPolicy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Goal {
    pub raw_text: String,
    pub intent_type: IntentType,
    pub desired_outcome: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum IntentType {
    CodeRepair,
    FileOperation,
    DataAnalysis,
    SystemMaintenance,
    Generic,
}

impl IntentType {
    pub fn detect(text: &str) -> Self {
        let lower = text.to_lowercase();
        if lower.contains("test") || lower.contains("fix") || lower.contains("bug") {
            Self::CodeRepair
        } else if lower.contains("file") || lower.contains("duplicate") || lower.contains("clean") {
            Self::FileOperation
        } else if lower.contains("analyze") || lower.contains("report") || lower.contains("data") {
            Self::DataAnalysis
        } else if lower.contains("maintain")
            || lower.contains("optimize")
            || lower.contains("update")
        {
            Self::SystemMaintenance
        } else {
            Self::Generic
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Constraints {
    pub budget: Budget,
    pub risk: Risk,
    pub time_limit_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Budget {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Risk {
    Low,
    Medium,
    High,
}

impl Risk {
    pub fn score(&self) -> f64 {
        match self {
            Risk::Low => 0.2,
            Risk::Medium => 0.5,
            Risk::High => 0.85,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RollbackPolicy {
    pub enabled: bool,
    pub strategy: RollbackStrategy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RollbackStrategy {
    Snapshot,
    None,
}

impl Intent {
    pub fn new(goal_text: &str) -> Self {
        let intent_type = IntentType::detect(goal_text);
        Self {
            id: format!("intent_{}", chrono::Utc::now().timestamp()),
            goal: Goal {
                raw_text: goal_text.to_string(),
                intent_type,
                desired_outcome: goal_text.to_string(),
            },
            constraints: Constraints {
                budget: Budget::Medium,
                risk: Risk::Medium,
                time_limit_seconds: 120,
            },
            allowed_capabilities: vec![],
            forbidden_capabilities: vec!["delete_files".to_string()],
            rollback_policy: RollbackPolicy {
                enabled: true,
                strategy: RollbackStrategy::Snapshot,
            },
        }
    }
}
