use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityDecision {
    pub allowed: bool,
    pub reason: String,
}

pub struct SecurityGateway;

impl SecurityGateway {
    pub fn check_capability(capability: &str, forbidden: &[String]) -> SecurityDecision {
        if forbidden.contains(&capability.to_string()) {
            return SecurityDecision {
                allowed: false,
                reason: format!("Capability '{}' is forbidden", capability),
            };
        }

        let dangerous = ["delete_files", "network_access", "system_shutdown"];
        if dangerous.contains(&capability) {
            return SecurityDecision {
                allowed: false,
                reason: format!("Capability '{}' requires approval", capability),
            };
        }

        SecurityDecision {
            allowed: true,
            reason: "Allowed".to_string(),
        }
    }

    pub fn scan_injection(input: &str) -> SecurityDecision {
        let lower = input.to_lowercase();
        let threats = [
            "ignore previous",
            "ignore all instructions",
            "you are now",
            "override system",
        ];

        for threat in threats {
            if lower.contains(threat) {
                return SecurityDecision {
                    allowed: false,
                    reason: format!("Injection detected: {}", threat),
                };
            }
        }

        SecurityDecision {
            allowed: true,
            reason: "Safe".to_string(),
        }
    }
}
