use crate::llm::LLMClient;

const APPROACHES: [&str; 5] = [
    "simple and direct, easy to understand",
    "with comprehensive error handling using Result",
    "optimized and efficient",
    "using standard library functions where possible",
    "with detailed edge case handling",
];

pub struct SolutionGenerator {
    llm: LLMClient,
}

impl SolutionGenerator {
    pub fn new(model: &str) -> Self {
        Self {
            llm: LLMClient::new(model),
        }
    }

    /// Number of distinct approaches `generate_solution` can take.
    pub fn approach_count() -> usize {
        APPROACHES.len()
    }

    /// Generate one solution using approach `index` (wraps around).
    /// None when the model produced nothing.
    pub fn generate_solution(
        &self,
        task: &str,
        language: &str,
        context: &str,
        index: usize,
    ) -> Option<String> {
        let approach = APPROACHES[index % APPROACHES.len()];
        let prompt = self.build_prompt(task, language, context, approach);
        let response = self.llm.generate_code(&prompt, language);
        (response.success && !response.content.is_empty()).then_some(response.content)
    }

    /// Generate multiple solutions with different approaches
    pub fn generate_solutions(
        &self,
        task: &str,
        language: &str,
        context: &str,
        count: usize,
    ) -> Vec<String> {
        (0..count.min(APPROACHES.len()))
            .filter_map(|i| self.generate_solution(task, language, context, i))
            .collect()
    }

    fn build_prompt(&self, task: &str, language: &str, context: &str, approach: &str) -> String {
        format!(
            r#"You are a senior {lang} engineer writing production code.

CONTEXT FROM PAST EXPERIENCE:
{context}

TASK: {task}

APPROACH: Write it {approach}.

STRICT RULES:
- Output ONLY raw {lang} source code
- NO explanations, NO markdown, NO backticks
- NO mathematical notation, NO LaTeX, NO $ symbols
- MUST include a main function with test cases
- MUST compile without errors
- Use idiomatic {lang} patterns

SELF-CHECK: Before outputting, verify:
- All types are correct
- All patterns are exhaustive
- All variables are declared
- No syntax errors

OUTPUT ONLY THE CODE:"#,
            lang = language,
            task = task,
            context = context,
            approach = approach
        )
    }
}
