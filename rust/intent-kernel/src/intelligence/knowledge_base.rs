use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolutionRecord {
    pub task: String,
    pub code: String,
    pub language: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorFix {
    pub error_code: String,
    pub error_message: String,
    pub category: String,
    pub fix_instruction: String,
    pub frequency: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Reflection {
    pub task: String,
    pub error_summary: String,
    pub lesson: String,
    pub timestamp: String,
}

#[derive(Debug, Default, Serialize, Deserialize)]
pub struct KnowledgeBase {
    pub successful_solutions: Vec<SolutionRecord>,
    pub error_fixes: Vec<ErrorFix>,
    pub reflections: Vec<Reflection>,
}

impl KnowledgeBase {
    pub fn load(path: &str) -> Self {
        let p = PathBuf::from(path);
        if p.exists() {
            fs::read_to_string(&p)
                .ok()
                .and_then(|s| serde_json::from_str(&s).ok())
                .unwrap_or_default()
        } else {
            Self::default()
        }
    }

    pub fn save(&self, path: &str) -> anyhow::Result<()> {
        let p = PathBuf::from(path);
        if let Some(parent) = p.parent() {
            fs::create_dir_all(parent)?;
        }
        let json = serde_json::to_string_pretty(self)?;
        fs::write(&p, json)?;
        Ok(())
    }

    /// Record a successful solution
    pub fn record_success(&mut self, task: &str, code: &str, language: &str) {
        self.successful_solutions.push(SolutionRecord {
            task: task.to_string(),
            code: code.to_string(),
            language: language.to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
        });
    }

    /// Record an error and its fix
    pub fn record_error_fix(
        &mut self,
        error_code: &str,
        error_message: &str,
        category: &str,
        fix_instruction: &str,
    ) {
        // Check if this error already exists
        if let Some(existing) = self
            .error_fixes
            .iter_mut()
            .find(|e| e.error_code == error_code && e.category == category)
        {
            existing.frequency += 1;
        } else {
            self.error_fixes.push(ErrorFix {
                error_code: error_code.to_string(),
                error_message: error_message.to_string(),
                category: category.to_string(),
                fix_instruction: fix_instruction.to_string(),
                frequency: 1,
            });
        }
    }

    /// Record a reflection (lesson learned)
    pub fn record_reflection(&mut self, task: &str, error_summary: &str, lesson: &str) {
        self.reflections.push(Reflection {
            task: task.to_string(),
            error_summary: error_summary.to_string(),
            lesson: lesson.to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
        });
    }

    /// Get relevant context for a new task
    pub fn get_context(&self, task: &str, language: &str) -> String {
        let mut context = String::new();

        // Add relevant successful solutions
        let relevant: Vec<&SolutionRecord> = self
            .successful_solutions
            .iter()
            .filter(|s| s.language == language)
            .filter(|s| Self::is_relevant(task, &s.task))
            .take(2)
            .collect();

        if !relevant.is_empty() {
            context.push_str("RELEVANT PAST SUCCESSFUL SOLUTIONS:\n");
            for sol in relevant {
                context.push_str(&format!("Task: {}\n", sol.task));
                context.push_str(&format!("Code:\n{}\n---\n", sol.code));
            }
        }

        // Add common error fixes for this language
        if !self.error_fixes.is_empty() {
            context.push_str("\nCOMMON ERRORS TO AVOID:\n");
            let mut sorted_fixes = self.error_fixes.clone();
            sorted_fixes.sort_by(|a, b| b.frequency.cmp(&a.frequency));
            for fix in sorted_fixes.iter().take(3) {
                context.push_str(&format!(
                    "- [{}] {}: {}\n",
                    fix.category, fix.error_message, fix.fix_instruction
                ));
            }
        }

        // Add reflections
        if !self.reflections.is_empty() {
            context.push_str("\nLESSONS LEARNED:\n");
            for reflection in self.reflections.iter().rev().take(2) {
                context.push_str(&format!("- {}\n", reflection.lesson));
            }
        }

        context
    }

    fn is_relevant(new_task: &str, past_task: &str) -> bool {
        let new_lower = new_task.to_lowercase();
        let past_lower = past_task.to_lowercase();

        let new_words: Vec<&str> = new_lower.split_whitespace().collect();
        let past_words: Vec<&str> = past_lower.split_whitespace().collect();

        let common = new_words.iter().filter(|w| past_words.contains(w)).count();

        common >= 2
    }

    pub fn summary(&self) -> String {
        format!(
            "Solutions: {}, Error fixes: {}, Reflections: {}",
            self.successful_solutions.len(),
            self.error_fixes.len(),
            self.reflections.len()
        )
    }
}
