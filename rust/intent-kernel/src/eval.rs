use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationResult {
    pub case_id: String,
    pub passed: bool,
    pub scores: EvalScores,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct EvalScores {
    pub success_score: f64,
    pub safety_score: f64,
    pub autonomy_quotient: f64,
}

pub struct Evaluator;

impl Evaluator {
    pub fn evaluate(plan: &crate::plan::PlanGraph) -> EvaluationResult {
        let safety = 1.0 - plan.risk_report.total_risk.min(1.0);
        let success = if plan.nodes.is_empty() { 0.0 } else { 1.0 };
        let aq = (success * safety * 10.0).min(10.0);

        EvaluationResult {
            case_id: plan.intent_id.clone(),
            passed: !plan.nodes.is_empty(),
            scores: EvalScores {
                success_score: success,
                safety_score: safety,
                autonomy_quotient: aq,
            },
        }
    }
}
