use crate::llm::LLMClient;

pub struct SelfReviewer {
    llm: LLMClient,
}

impl SelfReviewer {
    pub fn new(model: &str) -> Self {
        Self {
            llm: LLMClient::new(model),
        }
    }

    /// Review code and return fixed version if issues found
    pub fn review_and_fix(&self, code: &str, language: &str) -> String {
        let prompt = format!(
            r#"You are a senior {lang} code reviewer. Review this code for errors.

CODE TO REVIEW:
{code}

CHECK FOR:
1. Syntax errors (missing semicolons, unmatched braces)
2. Type mismatches
3. Non-exhaustive pattern matches
4. Missing main function
5. Undeclared variables
6. Mathematical notation or non-code text
7. Ownership/borrow issues

If the code has issues, output the FIXED version.
If the code is correct, output it unchanged.

OUTPUT ONLY THE {lang_upper} CODE. No explanations:"#,
            lang = language,
            code = code,
            lang_upper = language.to_uppercase()
        );

        let response = self.llm.generate_code(&prompt, language);

        if response.success && !response.content.is_empty() {
            response.content
        } else {
            code.to_string()
        }
    }
}
