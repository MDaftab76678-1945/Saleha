use crate::intelligence::error_analysis::ErrorAnalyzer;
use crate::intelligence::knowledge_base::KnowledgeBase;
use crate::intelligence::self_review::SelfReviewer;
use crate::intelligence::solution_gen::SolutionGenerator;
use std::process::Command;

pub struct ReflexionResult {
    pub success: bool,
    pub code: String,
    pub output: String,
    pub attempts: usize,
    pub reflections: Vec<String>,
    pub final_error: Option<String>,
}

pub struct ReflexionEngine {
    model: String,
    analyzer: ErrorAnalyzer,
    knowledge: KnowledgeBase,
    knowledge_path: String,
    max_attempts: usize,
}

impl ReflexionEngine {
    pub fn new(model: &str, knowledge_path: &str, max_attempts: usize) -> Self {
        let knowledge = KnowledgeBase::load(knowledge_path);
        Self {
            model: model.to_string(),
            analyzer: ErrorAnalyzer::new(),
            knowledge,
            knowledge_path: knowledge_path.to_string(),
            max_attempts,
        }
    }

    pub fn solve(&mut self, task: &str, language: &str, output_path: &str) -> ReflexionResult {
        println!("\n╔═══════════════════════════════════════════════════════╗");
        println!("║  REFLEXION ENGINE - INTELLIGENT PROBLEM SOLVING       ║");
        println!("╚═══════════════════════════════════════════════════════╝\n");
        println!("[TASK] {}", task);
        println!("[LANGUAGE] {}", language);
        println!("[KNOWLEDGE BASE] {}", self.knowledge.summary());
        println!("[MAX ATTEMPTS] {}\n", self.max_attempts);

        let mut reflections: Vec<String> = Vec::new();
        let mut best_code = String::new();
        let mut final_error: Option<String> = None;

        for attempt in 1..=self.max_attempts {
            println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            println!("  ATTEMPT {}/{}", attempt, self.max_attempts);
            println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

            // Step 1: Get context from knowledge base
            let context = self.knowledge.get_context(task, language);
            if !context.is_empty() {
                println!("[KNOWLEDGE] Retrieved relevant context from past experience");
            }

            // Step 2: Generate multiple solutions
            println!("[GENERATE] Creating multiple solution approaches...");
            let generator = SolutionGenerator::new(&self.model);
            let solutions = generator.generate_solutions(task, language, &context, 3);

            if solutions.is_empty() {
                println!("[GENERATE] ✗ No solutions generated");
                final_error = Some("No solutions generated".to_string());
                continue;
            }
            println!("[GENERATE] ✓ Generated {} solutions", solutions.len());

            // Step 3: Self-review each solution
            println!("[SELF-REVIEW] LLM reviewing its own code...");
            let reviewer = SelfReviewer::new(&self.model);
            let reviewed: Vec<String> = solutions
                .iter()
                .map(|code| reviewer.review_and_fix(code, language))
                .collect();

            // Step 4: Try to compile each, pick first that works
            for (i, code) in reviewed.iter().enumerate() {
                std::fs::write(output_path, code).ok();

                let compile_result = self.compile_and_run(output_path, language);

                if compile_result.success {
                    println!("[VERIFY] ✓ Solution {} compiles and runs!", i + 1);
                    best_code = code.clone();

                    // Learn from success
                    self.knowledge.record_success(task, code, language);
                    self.knowledge.save(&self.knowledge_path).ok();
                    println!("[LEARN] ✓ Success recorded in knowledge base");

                    return ReflexionResult {
                        success: true,
                        code: best_code,
                        output: compile_result.output,
                        attempts: attempt,
                        reflections,
                        final_error: None,
                    };
                } else {
                    println!(
                        "[VERIFY] ✗ Solution {} failed: {}",
                        i + 1,
                        compile_result.error_summary()
                    );

                    // Analyze error
                    if let Some(parsed) = self.analyzer.parse(&compile_result.stderr) {
                        let strategy = self.analyzer.get_fix_strategy(&parsed);

                        println!(
                            "[ANALYZE] Category: {} | {}",
                            strategy.category.name(),
                            strategy.description
                        );

                        // Record error fix
                        self.knowledge.record_error_fix(
                            &parsed.code.clone().unwrap_or_default(),
                            &parsed.message,
                            strategy.category.name(),
                            &strategy.instruction,
                        );

                        // Reflect
                        let lesson = format!(
                            "When {}, avoid {} by {}",
                            task, strategy.description, strategy.instruction
                        );
                        reflections.push(lesson.clone());
                        self.knowledge
                            .record_reflection(task, &parsed.message, &lesson);

                        final_error = Some(parsed.message.clone());
                    }
                }
            }

            if attempt < self.max_attempts {
                println!("[REFLECT] Analyzing failures, adapting strategy...");
                self.knowledge.save(&self.knowledge_path).ok();
            }
        }

        // Save knowledge even on failure
        self.knowledge.save(&self.knowledge_path).ok();

        ReflexionResult {
            success: false,
            code: best_code,
            output: String::new(),
            attempts: self.max_attempts,
            reflections,
            final_error,
        }
    }

    fn compile_and_run(&self, path: &str, language: &str) -> CompileResult {
        match language {
            "rust" => {
                let exe = "reflexion_test.exe";

                // Windows requires .\ prefix to run exe in current directory
                let exe_run_path = if cfg!(windows) {
                    format!(".\\{}", exe)
                } else {
                    format!("./{}", exe)
                };

                let compile = Command::new("rustc").args(&[path, "-o", exe]).output();

                match compile {
                    Ok(output) if output.status.success() => {
                        let run = Command::new(&exe_run_path).output();
                        let _ = std::fs::remove_file(exe);

                        match run {
                            Ok(run_output) if run_output.status.success() => CompileResult {
                                success: true,
                                output: String::from_utf8_lossy(&run_output.stdout).to_string(),
                                stderr: String::new(),
                            },
                            Ok(run_output) => CompileResult {
                                success: false,
                                output: String::new(),
                                stderr: String::from_utf8_lossy(&run_output.stderr).to_string(),
                            },
                            Err(e) => CompileResult {
                                success: false,
                                output: String::new(),
                                stderr: format!("Run failed: {}", e),
                            },
                        }
                    }
                    Ok(output) => CompileResult {
                        success: false,
                        output: String::new(),
                        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
                    },
                    Err(e) => CompileResult {
                        success: false,
                        output: String::new(),
                        stderr: format!("rustc not found: {}", e),
                    },
                }
            }
            "python" => {
                let run = Command::new("python").args(&[path]).output();
                match run {
                    Ok(output) if output.status.success() => CompileResult {
                        success: true,
                        output: String::from_utf8_lossy(&output.stdout).to_string(),
                        stderr: String::new(),
                    },
                    Ok(output) => CompileResult {
                        success: false,
                        output: String::new(),
                        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
                    },
                    Err(e) => CompileResult {
                        success: false,
                        output: String::new(),
                        stderr: format!("python not found: {}", e),
                    },
                }
            }
            _ => CompileResult {
                success: true,
                output: "No verifier for this language".to_string(),
                stderr: String::new(),
            },
        }
    }
}

struct CompileResult {
    success: bool,
    output: String,
    stderr: String,
}

impl CompileResult {
    fn error_summary(&self) -> String {
        let first_line = self.stderr.lines().next().unwrap_or("Unknown error");
        if first_line.len() > 100 {
            format!("{}...", &first_line[..100])
        } else {
            first_line.to_string()
        }
    }
}
