use std::collections::HashMap;

/// Represents a potential action an agent wants to take.
#[derive(Debug, Clone)]
pub struct AgentAction {
    pub action_type: String, // e.g., "transfer_funds", "execute_code"
    pub parameters: HashMap<String, String>,
    pub estimated_risk_score: f32, // From the Neural Net (LLM)
}

/// The Symbolic Rule Engine.
/// Contains hard-coded, mathematically provable safety rules.
pub struct SymbolicGuardrail {
    rules: Vec<SafetyRule>,
}

#[derive(Debug, Clone)]
pub struct SafetyRule {
    pub id: String,
    pub description: String,
    // In production, this would be an AST or a Prolog clause.
    // Here we use a closure for simplicity in Rust.
    pub check: fn(&AgentAction) -> bool, 
}

impl SymbolicGuardrail {
    pub fn new() -> Self {
        Self {
            rules: vec![
                SafetyRule {
                    id: "RULE_001".to_string(),
                    description: "Cannot transfer more than 10% of total wallet balance in a single tx".to_string(),
                    check: |action: &AgentAction| {
                        if action.action_type == "transfer_funds" {
                            if let Some(amount) = action.parameters.get("amount") {
                                if let Some(total) = action.parameters.get("total_balance") {
                                    let amt: f32 = amount.parse().unwrap_or(0.0);
                                    let tot: f32 = total.parse().unwrap_or(1.0);
                                    return (amt / tot) <= 0.10;
                                }
                            }
                        }
                        true // Pass if not a transfer
                    },
                },
                SafetyRule {
                    id: "RULE_002".to_string(),
                    description: "Cannot execute code containing 'rm -rf' or 'DROP TABLE'".to_string(),
                    check: |action: &AgentAction| {
                        if action.action_type == "execute_code" {
                            if let Some(code) = action.parameters.get("code_snippet") {
                                return !code.contains("rm -rf") && !code.contains("DROP TABLE");
                            }
                        }
                        true
                    },
                },
            ],
        }
    }

    /// Evaluates an action against all symbolic rules.
    pub fn evaluate(&self, action: &AgentAction) -> GuardrailResult {
        for rule in &self.rules {
            if !(rule.check)(action) {
                return GuardrailResult {
                    is_safe: false,
                    violated_rule: Some(rule.id.clone()),
                    reason: Some(rule.description.clone()),
                };
            }
        }

        // If all symbolic rules pass, check the neural risk score.
        if action.estimated_risk_score > 0.8 {
            return GuardrailResult {
                is_safe: false,
                violated_rule: Some("NEURAL_RISK_THRESHOLD".to_string()),
                reason: Some("LLM estimated risk score too high".to_string()),
            };
        }

        GuardrailResult {
            is_safe: true,
            violated_rule: None,
            reason: None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct GuardrailResult {
    pub is_safe: bool,
    pub violated_rule: Option<String>,
    pub reason: Option<String>,
}
