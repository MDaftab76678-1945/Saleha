use serde::{Deserialize, Serialize};
use std::io::Write;
use std::process::{Command, Stdio};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LLMResponse {
    pub content: String,
    pub model: String,
    pub success: bool,
}

pub struct LLMClient {
    model: String,
    available: bool,
}

impl LLMClient {
    pub fn new(model: &str) -> Self {
        let available = Self::check_ollama();

        if available {
            println!("[LLM] ✓ Ollama detected. Model: {}", model);
        } else {
            println!("[LLM] ⚠ Ollama not found. Using template fallback.");
        }

        Self {
            model: model.to_string(),
            available,
        }
    }

    fn get_language_rules(language: &str) -> String {
        match language {
            "rust" => "\
                - Use proper ownership (borrowing, lifetimes)\n\
                - Use Result<T, E> for error handling\n\
                - Use match for exhaustive pattern matching\n\
                - No unwrap() unless absolutely necessary\n\
                - Use snake_case for functions/variables\n\
                - Use CamelCase for types\n\
                - Include #[derive(Debug)] where useful\n\
                - Use u64/i64 for numbers unless specified\n\
                - Never use negative numbers with unsigned types"
                .to_string(),

            "python" => "\
                - Use type hints\n\
                - Use docstrings\n\
                - Handle exceptions with try/except\n\
                - Use f-strings for formatting\n\
                - Follow PEP 8\n\
                - Use if __name__ == '__main__' guard\n\
                - Include test cases with assert"
                .to_string(),

            "javascript" => "\
                - Use const/let, never var\n\
                - Use arrow functions where appropriate\n\
                - Handle errors with try/catch\n\
                - Use strict equality (===)\n\
                - Include test cases with console.assert"
                .to_string(),

            _ => "- Write clean, idiomatic code\n\
                  - Handle errors properly\n\
                  - Include test cases"
                .to_string(),
        }
    }

    fn check_ollama() -> bool {
        Command::new("ollama")
            .arg("--version")
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    }

    pub fn is_available(&self) -> bool {
        self.available
    }

    pub fn generate_code(&self, task: &str, language: &str) -> LLMResponse {
        if self.available {
            self.generate_with_ollama(task, language)
        } else {
            self.generate_with_template(task, language)
        }
    }

    fn generate_with_ollama(&self, task: &str, language: &str) -> LLMResponse {
        let prompt = format!(
            r#"SYSTEM: You are a senior {lang} engineer with 15+ years of experience.
You write production-ready, idiomatic {lang} code.
You NEVER output explanations, markdown, or commentary.
You output ONLY compilable source code.

TASK: {task}

OUTPUT FORMAT:
- Raw {lang} source code only
- No markdown fences
- No backticks
- No numbered lists
- No "here is" or "below is" phrases
- Must include a main function with test cases
- Must handle edge cases

LANGUAGE-SPECIFIC RULES FOR {lang_upper}:
{lang_rules}

SELF-VERIFICATION:
Before outputting, mentally compile the code.
Ensure all variables are declared.
Ensure all patterns are exhaustive.
Ensure all types match.
Ensure no syntax errors.

EXAMPLE OF CORRECT OUTPUT FORMAT:
fn add(a: i32, b: i32) -> i32 {{
    a + b
}}

fn main() {{
    assert_eq!(add(2, 3), 5);
    println!("Test passed");
}}

Now write the code for the task. Output ONLY the code:"#,
            lang = language,
            task = task,
            lang_upper = language.to_uppercase(),
            lang_rules = Self::get_language_rules(language),
        );

        println!("[LLM] Sending prompt to Ollama...");

        let mut child = match Command::new("ollama")
            .arg("run")
            .arg(&self.model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
        {
            Ok(child) => child,
            Err(error) => {
                println!("[LLM] Failed to spawn Ollama: {}", error);
                return self.generate_with_template(task, language);
            }
        };

        if let Some(mut stdin) = child.stdin.take() {
            if let Err(error) = stdin.write_all(prompt.as_bytes()) {
                println!("[LLM] Failed to write prompt: {}", error);
                return self.generate_with_template(task, language);
            }
        }

        match child.wait_with_output() {
            Ok(output) if output.status.success() => {
                let content = String::from_utf8_lossy(&output.stdout).to_string();
                let cleaned = Self::clean_code(&content);

                if cleaned.is_empty() {
                    println!("[LLM] Empty response from Ollama");
                    return self.generate_with_template(task, language);
                }

                println!("[LLM] ✓ Code generated successfully");

                LLMResponse {
                    content: cleaned,
                    model: self.model.clone(),
                    success: true,
                }
            }

            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr);
                println!("[LLM] Ollama failed: {}", stderr);
                self.generate_with_template(task, language)
            }

            Err(error) => {
                println!("[LLM] Failed to wait for Ollama: {}", error);
                self.generate_with_template(task, language)
            }
        }
    }

    fn generate_with_template(&self, task: &str, language: &str) -> LLMResponse {
        let code = match language {
            "rust" => format!(
                "// Auto-generated by Intent Kernel LLM\n\
                 // Task: {}\n\n\
                 fn main() {{\n\
                 \x20   println!(\"Executing: {}\");\n\
                 \x20   // TODO: Implement task logic\n\
                 }}\n",
                task, task
            ),

            "python" => format!(
                "# Auto-generated by Intent Kernel LLM\n\
                 # Task: {}\n\n\
                 def main():\n\
                 \x20   print(\"Executing: {}\")\n\
                 \x20   # TODO: Implement task logic\n\n\
                 if __name__ == \"__main__\":\n\
                 \x20   main()\n",
                task, task
            ),

            "javascript" => format!(
                "// Auto-generated by Intent Kernel LLM\n\
                 // Task: {}\n\n\
                 function main() {{\n\
                 \x20   console.log(\"Executing: {}\");\n\
                 \x20   // TODO: Implement task logic\n\
                 }}\n\n\
                 main();\n",
                task, task
            ),

            _ => format!(
                "// Auto-generated by Intent Kernel LLM\n\
                 // Task: {}\n\
                 // Language: {}\n",
                task, language
            ),
        };

        LLMResponse {
            content: code,
            model: "template-fallback".to_string(),
            success: true,
        }
    }

    fn clean_code(code: &str) -> String {
        // Step 1: Strip ANSI escape sequences
        let mut cleaned = String::new();
        let mut chars = code.chars().peekable();

        while let Some(c) = chars.next() {
            if c == '\x1b' {
                while let Some(&next) = chars.peek() {
                    chars.next();

                    if next.is_ascii_alphabetic() {
                        break;
                    }
                }
            } else {
                cleaned.push(c);
            }
        }

        // Step 2: Remove reasoning markers
        let reasoning_markers = [
            "...done thinking",
            "... done thinking",
            "Let me think",
            "I need to",
            "I should",
            "I will",
            "Let's",
            "Let me",
            "Testing this",
            "This implementation",
            "Final structure",
            "Note:",
            "Note that",
            "The use of",
            "Since performance",
            "Now we need to",
            "This converts",
            "Here is my approach",
            "My approach",
            "Step 1:",
            "Step 2:",
            "First,",
            "Second,",
            "Next,",
            "Finally,",
            "In conclusion",
            "To summarize",
            "Therefore,",
            "Thus,",
        ];

        for marker in &reasoning_markers {
            if let Some(pos) = cleaned.find(marker) {
                let rest = &cleaned[pos..];

                if let Some(end_pos) = rest.find("\n\n") {
                    cleaned = format!("{}{}", &cleaned[..pos], &rest[end_pos..]);
                } else {
                    cleaned = cleaned[..pos].to_string();
                }
            }
        }

        // Step 3: If multiple Rust function blocks exist,
        // extract the last one only.
        if let Some(last_fn_pos) = cleaned.rfind("\nfn ") {
            if let Some(first_fn_pos) = cleaned.find("fn ") {
                if first_fn_pos < last_fn_pos.saturating_sub(1) {
                    cleaned = cleaned[last_fn_pos + 1..].to_string();
                }
            }
        }

        // Step 4: Remove markdown fences/backticks
        cleaned = cleaned.replace("```rust", "");
        cleaned = cleaned.replace("```python", "");
        cleaned = cleaned.replace("```javascript", "");
        cleaned = cleaned.replace("```typescript", "");
        cleaned = cleaned.replace("```go", "");
        cleaned = cleaned.replace("```", "");
        cleaned = cleaned.replace('`', "");

        // Step 5: Filter explanation lines
        let lines: Vec<&str> = cleaned.lines().collect();
        let mut code_lines: Vec<&str> = Vec::new();
        let mut found_code_start = false;

        for line in &lines {
            let trimmed = line.trim();

            if trimmed.is_empty() && !found_code_start {
                continue;
            }

            let is_explanation = trimmed.starts_with("Here")
                || trimmed.starts_with("here")
                || trimmed.starts_with("Here's")
                || trimmed.starts_with("Below")
                || trimmed.starts_with("below")
                || trimmed.starts_with("The following")
                || trimmed.starts_with("This code")
                || trimmed.starts_with("This function")
                || trimmed.starts_with("Sure")
                || trimmed.starts_with("Certainly")
                || trimmed.starts_with("Note:")
                || trimmed.starts_with("Proof:")
                || trimmed.starts_with("Theorem:")
                || trimmed.starts_with("Lemma:")
                || trimmed.starts_with("Let ")
                || trimmed.starts_with("Suppose ")
                || trimmed.starts_with("Therefore")
                || trimmed.starts_with("Thus")
                || trimmed.starts_with("Hence")
                || trimmed.starts_with("For any")
                || trimmed.starts_with("For all")
                || trimmed.starts_with("Testing")
                || trimmed.starts_with("This implementation")
                || trimmed.starts_with("Final structure")
                || trimmed.starts_with("The use of")
                || trimmed.starts_with("Since ")
                || trimmed.starts_with("Now we")
                || trimmed.starts_with("This converts")
                || trimmed.starts_with("In summary")
                || trimmed.starts_with("To summarize")
                || trimmed.contains("appears correct")
                || trimmed.contains("done thinking")
                || trimmed.contains("approaches")
                || trimmed.contains("increases by")
                || trimmed.contains("decreases by")
                || trimmed.contains("multiplied by")
                || trimmed.contains("divided by")
                || (trimmed.chars().next().is_some_and(|c| c.is_ascii_digit())
                    && trimmed.len() > 2
                    && trimmed.chars().nth(1) == Some('.'));

            if is_explanation && !found_code_start {
                continue;
            }

            let is_code = trimmed.starts_with("fn ")
                || trimmed.starts_with("use ")
                || trimmed.starts_with("pub ")
                || trimmed.starts_with("struct ")
                || trimmed.starts_with("impl ")
                || trimmed.starts_with("mod ")
                || trimmed.starts_with("enum ")
                || trimmed.starts_with("trait ")
                || trimmed.starts_with("type ")
                || trimmed.starts_with("const ")
                || trimmed.starts_with("static ")
                || trimmed.starts_with("extern ")
                || trimmed.starts_with("#[")
                || trimmed.starts_with("def ")
                || trimmed.starts_with("import ")
                || trimmed.starts_with("from ")
                || trimmed.starts_with("class ")
                || trimmed.starts_with("async ")
                || trimmed.starts_with("function ")
                || trimmed.starts_with("let ")
                || trimmed.starts_with("var ")
                || trimmed.starts_with("//")
                || trimmed.starts_with("/*")
                || trimmed.starts_with("* ")
                || trimmed.starts_with("#!")
                || trimmed.starts_with("if __name__");

            if is_code {
                found_code_start = true;
            }

            if found_code_start {
                let mid_explanation = trimmed.starts_with("Testing")
                    || trimmed.starts_with("This implementation")
                    || trimmed.starts_with("Final structure")
                    || trimmed.starts_with("The use of")
                    || trimmed.starts_with("Since ")
                    || trimmed.starts_with("Now we")
                    || trimmed.starts_with("Note:")
                    || trimmed.contains("done thinking")
                    || trimmed.contains("appears correct")
                    || trimmed.contains("Edge case handled");

                if !mid_explanation {
                    code_lines.push(line);
                }
            }
        }

        cleaned = code_lines.join("\n");

        // Step 6: Remove remaining control characters
        cleaned = cleaned
            .chars()
            .filter(|c| *c == '\n' || *c == '\t' || !c.is_control())
            .collect();

        cleaned.trim().to_string()
    }
}
