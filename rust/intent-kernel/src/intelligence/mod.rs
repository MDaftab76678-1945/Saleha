pub mod error_analysis;
pub mod knowledge_base;
pub mod reflexion;
pub mod self_review;
pub mod solution_gen;

pub use error_analysis::{ErrorAnalyzer, ErrorCategory, FixStrategy, ParsedError};
pub use knowledge_base::KnowledgeBase;
pub use reflexion::ReflexionEngine;
pub use self_review::SelfReviewer;
pub use solution_gen::SolutionGenerator;
