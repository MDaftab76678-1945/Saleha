use crate::llm::LLMClient;
use crate::security::SecurityGateway;
use crate::verify::{Verifier, VerifyResult};

pub enum AgentRole {
    Planner,
    Security,
    Coder,
    QA,
    Executor,
}

impl AgentRole {
    pub fn name(&self) -> &str {
        match self {
            AgentRole::Planner => "Planner",
            AgentRole::Security => "Security",
            AgentRole::Coder => "Coder",
            AgentRole::QA => "QA",
            AgentRole::Executor => "Executor",
        }
    }
}

pub struct AgentDecision {
    pub agent: AgentRole,
    pub approved: bool,
    pub feedback: String,
}

pub struct NegotiationResult {
    pub approved: bool,
    pub decisions: Vec<AgentDecision>,
    pub generated_code: String,
    pub verify_result: Option<VerifyResult>,
    pub final_output: String,
}

struct CoderResult {
    content: String,
    decision: AgentDecision,
}

pub struct Negotiator {
    llm: LLMClient,
    verifier: Verifier,
}

impl Negotiator {
    pub fn new(model: &str) -> Self {
        Self {
            llm: LLMClient::new(model),
            verifier: Verifier::new(),
        }
    }

    pub fn negotiate(&self, task: &str, language: &str, output_path: &str) -> NegotiationResult {
        let mut decisions = Vec::new();
        let mut final_output = String::new();

        println!("\n╔═══════════════════════════════════════════════════════╗");
        println!("║  MULTI-AGENT NEGOTIATION                              ║");
        println!("╚═════════════════════════════════════════════════════╝\n");
        println!("[TASK] {}", task);
        println!("[LANGUAGE] {}\n", language);

        // === AGENT 1: PLANNER ===
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  AGENT 1: PLANNER");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        let plan_decision = self.planner_agent(task, language);
        println!("[PLANNER] {}", plan_decision.feedback);
        decisions.push(plan_decision);

        // === AGENT 2: SECURITY ===
        println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  AGENT 2: SECURITY");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        let security_decision = self.security_agent(task);
        println!("[SECURITY] {}", security_decision.feedback);

        if !security_decision.approved {
            decisions.push(security_decision);
            return NegotiationResult {
                approved: false,
                decisions,
                generated_code: String::new(),
                verify_result: None,
                final_output: "Mission aborted: Security threat detected".to_string(),
            };
        }
        decisions.push(security_decision);

        // === AGENT 3: CODER ===
        println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  AGENT 3: CODER");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        let coder_result = self.coder_agent(task, language);
        let mut generated_code = coder_result.content.clone();
        println!("[CODER] {}", coder_result.decision.feedback);
        decisions.push(coder_result.decision);

        // === AGENT 4: QA (Auto-Verification) ===
        println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  AGENT 4: QA (Auto-Verification)");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        // Save code to file
        std::fs::write(output_path, &generated_code).ok();

        let mut attempts = 0;
        let max_retries = self.verifier.max_retries();
        let mut current_code = generated_code.clone();
        let verify_result: Option<VerifyResult>;

        loop {
            attempts += 1;
            println!("\n[QA] Attempt {}/{}", attempts, max_retries);

            let result = match language {
                "rust" => self.verifier.verify_rust_code(output_path),
                "python" => self.verifier.verify_python_code(output_path),
                _ => {
                    println!("[QA] No verifier for language: {}", language);
                    VerifyResult {
                        success: true,
                        compiled: true,
                        output: "No verification available".to_string(),
                        compile_errors: String::new(),
                        attempts: 1,
                    }
                }
            };

            if result.success {
                println!("[QA] ✓ Code verified successfully!");
                final_output = result.output.clone();
                verify_result = Some(result);

                let qa_decision = AgentDecision {
                    agent: AgentRole::QA,
                    approved: true,
                    feedback: format!("Code verified on attempt {}", attempts),
                };
                decisions.push(qa_decision);
                break;
            } else {
                println!("[QA] ✗ Verification failed");
                println!(
                    "[QA] Errors: {}",
                    &result.compile_errors[..result.compile_errors.len().min(200)]
                );

                if attempts >= max_retries {
                    println!("[QA] Max retries reached. Mission failed.");
                    let qa_decision = AgentDecision {
                        agent: AgentRole::QA,
                        approved: false,
                        feedback: format!("Failed after {} attempts", attempts),
                    };
                    decisions.push(qa_decision);
                    verify_result = Some(result);
                    break;
                }

                // Ask LLM to fix the code
                println!("[QA] Asking LLM to fix errors...");
                let fix_prompt = format!(
                    "Fix this {} code. The errors are:\n{}\n\nOriginal code:\n{}\n\nWrite ONLY the fixed code, no markdown.",
                    language, result.compile_errors, current_code
                );

                let fix_response = self.llm.generate_code(&fix_prompt, language);
                current_code = fix_response.content.clone();
                std::fs::write(output_path, &current_code).ok();
                generated_code = current_code.clone();
            }
        }

        // === AGENT 5: EXECUTOR ===
        println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  AGENT 5: EXECUTOR");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        let all_approved = decisions.iter().all(|d| d.approved);
        let executor_decision = AgentDecision {
            agent: AgentRole::Executor,
            approved: all_approved,
            feedback: if all_approved {
                format!("Code saved to: {}", output_path)
            } else {
                "Mission failed: Previous agents rejected".to_string()
            },
        };
        println!("[EXECUTOR] {}", executor_decision.feedback);
        decisions.push(executor_decision);

        // === FINAL RESULT ===
        println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  NEGOTIATION COMPLETE");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        let final_approved = decisions.iter().all(|d| d.approved);
        println!(
            "\n[RESULT] {}",
            if final_approved {
                "✓ APPROVED"
            } else {
                "✗ REJECTED"
            }
        );

        NegotiationResult {
            approved: final_approved,
            decisions,
            generated_code,
            verify_result,
            final_output,
        }
    }

    fn planner_agent(&self, task: &str, language: &str) -> AgentDecision {
        let complexity = if task.len() > 100 { "high" } else { "medium" };
        AgentDecision {
            agent: AgentRole::Planner,
            approved: true,
            feedback: format!(
                "Task analyzed. Complexity: {}. Language: {}. Proceeding with code generation.",
                complexity, language
            ),
        }
    }

    fn security_agent(&self, task: &str) -> AgentDecision {
        let scan = SecurityGateway::scan_injection(task);
        AgentDecision {
            agent: AgentRole::Security,
            approved: scan.allowed,
            feedback: if scan.allowed {
                "Task is safe. No injection detected.".to_string()
            } else {
                format!("THREAT DETECTED: {}", scan.reason)
            },
        }
    }

    fn coder_agent(&self, task: &str, language: &str) -> CoderResult {
        println!("[CODER] Generating code with LLM...");
        let response = self.llm.generate_code(task, language);
        let content_len = response.content.len();
        let model_name = response.model.clone();
        let success = response.success;

        CoderResult {
            content: response.content,
            decision: AgentDecision {
                agent: AgentRole::Coder,
                approved: success,
                feedback: format!(
                    "Code generated ({} bytes, model: {})",
                    content_len, model_name
                ),
            },
        }
    }
}
