use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldModel {
    pub entities: HashMap<String, WorldEntity>,
    pub causal_rules: Vec<CausalRule>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldEntity {
    pub id: String,
    pub name: String,
    pub state: EntityState,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum EntityState {
    Healthy,
    Degraded,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CausalRule {
    pub action: String,
    pub effect: String,
    pub confidence: f64,
}

impl WorldModel {
    pub fn new() -> Self {
        Self {
            entities: HashMap::new(),
            causal_rules: Vec::new(),
        }
    }

    pub fn learn_rule(&mut self, action: &str, effect: &str, confidence: f64) {
        self.causal_rules.push(CausalRule {
            action: action.to_string(),
            effect: effect.to_string(),
            confidence,
        });
    }

    pub fn predict(&self, action: &str) -> Option<&CausalRule> {
        self.causal_rules
            .iter()
            .filter(|r| r.action == action)
            .max_by(|a, b| a.confidence.partial_cmp(&b.confidence).unwrap())
    }
}
