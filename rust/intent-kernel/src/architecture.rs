use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ArchitectureLayer {
    CognitiveCore,
    Memory,
    ExecutionCapability,
    VerificationProofSafety,
    Runtime,
    Llm,
    Ui,
}

impl ArchitectureLayer {
    pub fn name(self) -> &'static str {
        match self {
            Self::CognitiveCore => "Cognitive Core",
            Self::Memory => "Memory",
            Self::ExecutionCapability => "Execution/Capability",
            Self::VerificationProofSafety => "Verification/Proof/Safety",
            Self::Runtime => "Runtime",
            Self::Llm => "LLM",
            Self::Ui => "UI",
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct LayerMapping {
    pub layer: ArchitectureLayer,
    pub modules: &'static [&'static str],
    pub decision: &'static str,
    pub rationale: &'static str,
}

pub const V03_ARCHITECTURE_MAP: &[LayerMapping] = &[
    LayerMapping {
        layer: ArchitectureLayer::CognitiveCore,
        modules: &[
            "intent",
            "compiler",
            "plan",
            "eval",
            "agi",
            "intelligence::reflexion",
        ],
        decision: "retain + refactor",
        rationale: "Keep deterministic intent compilation as the stable core; keep reflexion as an experimental cognitive loop behind verification.",
    },
    LayerMapping {
        layer: ArchitectureLayer::Memory,
        modules: &["memory", "intelligence::knowledge_base"],
        decision: "retain + normalize later",
        rationale: "Both stores are useful, but v0.3 keeps their current JSON persistence and defers a unified memory schema.",
    },
    LayerMapping {
        layer: ArchitectureLayer::ExecutionCapability,
        modules: &["capability", "executor"],
        decision: "retain + harden now",
        rationale: "The capability registry and executor are the real actuator boundary and must share a single contract.",
    },
    LayerMapping {
        layer: ArchitectureLayer::VerificationProofSafety,
        modules: &["security", "proof", "verify", "runtime::PlanValidator"],
        decision: "retain + harden now",
        rationale: "SALEHA-style validation belongs before execution and must produce durable proof events after execution.",
    },
    LayerMapping {
        layer: ArchitectureLayer::Runtime,
        modules: &["runtime", "main::run_mission", "main::run_coding_mission"],
        decision: "create thin boundary",
        rationale: "v0.3 introduces validation as a runtime gate without rewriting orchestration wholesale.",
    },
    LayerMapping {
        layer: ArchitectureLayer::Llm,
        modules: &["llm", "negotiation", "intelligence::solution_gen", "intelligence::self_review"],
        decision: "retain as adapter + experimental workflows",
        rationale: "Ollama/template generation remains useful, but generated code must remain downstream of safety and verification.",
    },
    LayerMapping {
        layer: ArchitectureLayer::Ui,
        modules: &["main"],
        decision: "retain CLI",
        rationale: "The CLI is the only UI in v0.3; richer UI and service APIs are deferred.",
    },
];
