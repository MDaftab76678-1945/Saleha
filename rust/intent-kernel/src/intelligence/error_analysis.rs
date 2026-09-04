use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ErrorCategory {
    TypeMismatch,
    MissingImport,
    UndefinedValue,
    PatternMatch,
    Ownership,
    Syntax,
    MissingMain,
    TraitBound,
    WrongArgs,
    NoField,
    MathNotation,
    Other,
}

impl ErrorCategory {
    pub fn name(&self) -> &str {
        match self {
            ErrorCategory::TypeMismatch => "TypeMismatch",
            ErrorCategory::MissingImport => "MissingImport",
            ErrorCategory::UndefinedValue => "UndefinedValue",
            ErrorCategory::PatternMatch => "PatternMatch",
            ErrorCategory::Ownership => "Ownership",
            ErrorCategory::Syntax => "Syntax",
            ErrorCategory::MissingMain => "MissingMain",
            ErrorCategory::TraitBound => "TraitBound",
            ErrorCategory::WrongArgs => "WrongArgs",
            ErrorCategory::NoField => "NoField",
            ErrorCategory::MathNotation => "MathNotation",
            ErrorCategory::Other => "Other",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedError {
    pub code: Option<String>,
    pub message: String,
    pub file: String,
    pub line: usize,
    pub column: usize,
    pub category: ErrorCategory,
    pub raw: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FixStrategy {
    pub category: ErrorCategory,
    pub description: String,
    pub instruction: String,
}

pub struct ErrorAnalyzer;

impl ErrorAnalyzer {
    pub fn new() -> Self {
        Self
    }

    /// Parse rustc output into structured error
    pub fn parse(&self, compiler_output: &str) -> Option<ParsedError> {
        let lines: Vec<&str> = compiler_output.lines().collect();
        if lines.is_empty() {
            return None;
        }

        let mut code: Option<String> = None;
        let mut message = String::new();
        let mut file = String::new();
        let mut line: usize = 0;
        let mut column: usize = 0;

        for l in &lines {
            let trimmed = l.trim();

            // Extract error code and message: "error[E0308]: mismatched types"
            if trimmed.starts_with("error") {
                if let Some(start) = trimmed.find('[') {
                    if let Some(end) = trimmed.find(']') {
                        code = Some(trimmed[start + 1..end].to_string());
                    }
                }
                if let Some(colon_pos) = trimmed.find(':') {
                    message = trimmed[colon_pos + 1..].trim().to_string();
                }
            }

            // Extract location: " --> src/main.rs:10:5"
            if trimmed.starts_with("-->") {
                let loc = trimmed.trim_start_matches("-->").trim();
                let parts: Vec<&str> = loc.split(':').collect();
                if parts.len() >= 3 {
                    file = parts[0].to_string();
                    line = parts[1].parse().unwrap_or(0);
                    column = parts[2].parse().unwrap_or(0);
                }
            }
        }

        if message.is_empty() {
            return None;
        }

        let category = self.categorize(&code, &message, compiler_output);

        Some(ParsedError {
            code,
            message,
            file,
            line,
            column,
            category,
            raw: compiler_output.to_string(),
        })
    }

    /// Categorize error based on code and message
    fn categorize(&self, code: &Option<String>, message: &str, raw: &str) -> ErrorCategory {
        // Check for math notation first
        if raw.contains("$")
            || raw.contains("\\pm")
            || raw.contains("\\times")
            || raw.contains("\\sqrt")
            || raw.contains("\\frac")
        {
            return ErrorCategory::MathNotation;
        }

        let msg_lower = message.to_lowercase();
        let code_str = code.clone().unwrap_or_default();

        match code_str.as_str() {
            "E0308" => ErrorCategory::TypeMismatch,
            "E0433" | "E0432" => ErrorCategory::MissingImport,
            "E0425" | "E0412" => ErrorCategory::UndefinedValue,
            "E0004" | "E0408" => ErrorCategory::PatternMatch,
            "E0382" | "E0384" => ErrorCategory::Ownership,
            "E0601" => ErrorCategory::MissingMain,
            "E0277" | "E0282" => ErrorCategory::TraitBound,
            "E0061" => ErrorCategory::WrongArgs,
            "E0609" | "E0560" => ErrorCategory::NoField,
            _ => {
                if msg_lower.contains("mismatched types") {
                    ErrorCategory::TypeMismatch
                } else if msg_lower.contains("cannot find") || msg_lower.contains("unresolved") {
                    ErrorCategory::MissingImport
                } else if msg_lower.contains("not found in crate")
                    || msg_lower.contains("not found in this scope")
                {
                    ErrorCategory::UndefinedValue
                } else if msg_lower.contains("non-exhaustive") || msg_lower.contains("pattern") {
                    ErrorCategory::PatternMatch
                } else if msg_lower.contains("borrow") || msg_lower.contains("moved") {
                    ErrorCategory::Ownership
                } else if msg_lower.contains("main") && msg_lower.contains("not found") {
                    ErrorCategory::MissingMain
                } else if msg_lower.contains("expected") && msg_lower.contains("found") {
                    ErrorCategory::TypeMismatch
                } else {
                    ErrorCategory::Syntax
                }
            }
        }
    }

    /// Generate fix strategy based on category
    pub fn get_fix_strategy(&self, error: &ParsedError) -> FixStrategy {
        let (description, instruction) = match error.category {
            ErrorCategory::TypeMismatch => (
                "Types don't match. A value of one type is being used where another is expected."
                    .to_string(),
                "Check the expected type vs actual type. Use proper conversion with 'as' or '.into()'. \
                 Ensure numeric literals match the expected type (i32, i64, u64). \
                 Don't use negative numbers with unsigned types (u64, u32)."
                    .to_string(),
            ),
            ErrorCategory::MissingImport => (
                "A module, crate, or item is not in scope.".to_string(),
                "Add the appropriate 'use' statement at the top. \
                 For standard library: 'use std::collections::HashMap;'. \
                 Check for typos in module names."
                    .to_string(),
            ),
            ErrorCategory::UndefinedValue => (
                "A variable or function is used but not defined.".to_string(),
                "Ensure all variables are declared before use. \
                 Check for typos. Ensure functions are defined in scope."
                    .to_string(),
            ),
            ErrorCategory::PatternMatch => (
                "Match expression doesn't cover all possible cases.".to_string(),
                "Add all missing pattern arms. Use '_ => ...' as a catch-all if appropriate. \
                 For Result<T,E>, handle both Ok(_) and Err(_). \
                 For Option<T>, handle both Some(_) and None."
                    .to_string(),
            ),
            ErrorCategory::Ownership => (
                "Borrow checker error: value moved or borrowed incorrectly.".to_string(),
                "Use .clone() if you need to keep the original. \
                 Use references (&) to borrow instead of move. \
                 Check variable lifetimes."
                    .to_string(),
            ),
            ErrorCategory::Syntax => (
                "Syntax error in the code.".to_string(),
                "Check for missing semicolons, unmatched braces/parentheses. \
                 Ensure no explanatory text or markdown is in the code. \
                 Remove any non-code content."
                    .to_string(),
            ),
            ErrorCategory::MissingMain => (
                "No main function found.".to_string(),
                "Add 'fn main() { ... }' with test cases that demonstrate the code."
                    .to_string(),
            ),
            ErrorCategory::TraitBound => (
                "Type doesn't satisfy required trait or needs annotation.".to_string(),
                "Add explicit type annotations. Ensure types implement required traits. \
                 Use turbofish syntax ::<T> if needed."
                    .to_string(),
            ),
            ErrorCategory::WrongArgs => (
                "Function called with wrong number of arguments.".to_string(),
                "Check the function signature and pass the correct number and type of arguments."
                    .to_string(),
            ),
            ErrorCategory::NoField => (
                "Accessing a field that doesn't exist on the type.".to_string(),
                "Check the struct definition. Use the correct field name. \
                 Ensure you're accessing the right type."
                    .to_string(),
            ),
            ErrorCategory::MathNotation => (
                "Mathematical notation or LaTeX leaked into the code.".to_string(),
                "Remove ALL mathematical notation, LaTeX, symbols like $, \\pm, \\times. \
                 Output ONLY pure Rust code with no formulas or explanations."
                    .to_string(),
            ),
            ErrorCategory::Other => (
                "Unclassified error.".to_string(),
                "Review the error message carefully and fix the specific issue mentioned."
                    .to_string(),
            ),
        };

        FixStrategy {
            category: error.category.clone(),
            description,
            instruction,
        }
    }
}
