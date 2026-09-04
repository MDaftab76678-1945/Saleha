use serde::{Deserialize, Serialize};

use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryNode {
    pub id: String,
    pub kind: MemoryKind,
    pub content: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum MemoryKind {
    Mission,
    Playbook,
    Lesson,
}

#[derive(Debug, Default, Serialize, Deserialize)]
pub struct MemoryStore {
    nodes: Vec<MemoryNode>,
}

impl MemoryStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn load(path: &str) -> Self {
        Self::read(path).unwrap_or_default()
    }

    pub fn read(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let path = path.as_ref();
        if !path.exists() {
            return Ok(Self::default());
        }

        let content = fs::read_to_string(path)?;
        Ok(serde_json::from_str(&content)?)
    }

    pub fn save(&self, path: &str) -> anyhow::Result<()> {
        if let Some(parent) = PathBuf::from(path).parent() {
            fs::create_dir_all(parent)?;
        }
        let json = serde_json::to_string_pretty(self)?;
        fs::write(path, json)?;
        Ok(())
    }

    pub fn record_mission(&mut self, goal: &str, success: bool) {
        self.nodes.push(MemoryNode {
            id: format!(
                "mem_{}",
                chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
            ),
            kind: MemoryKind::Mission,
            content: format!("{} | success={}", goal, success),
            timestamp: chrono::Utc::now().to_rfc3339(),
        });
    }

    pub fn record_playbook(&mut self, name: &str, steps: Vec<String>) {
        self.nodes.push(MemoryNode {
            id: format!(
                "pb_{}",
                chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
            ),
            kind: MemoryKind::Playbook,
            content: format!("{}: {:?}", name, steps),
            timestamp: chrono::Utc::now().to_rfc3339(),
        });
    }

    pub fn retrieve(&self, query: &str) -> Vec<&MemoryNode> {
        let query_lower = query.to_lowercase();
        self.nodes
            .iter()
            .filter(|n| {
                let content_lower = n.content.to_lowercase();
                query_lower
                    .split_whitespace()
                    .any(|w| content_lower.contains(w))
            })
            .collect()
    }

    pub fn nodes(&self) -> &[MemoryNode] {
        &self.nodes
    }

    pub fn record_compilation(
        &self,
        intent: &crate::intent::Intent,
        plan: &crate::plan::PlanGraph,
    ) {
        // In a full implementation, this would store compilation patterns
        // For now, we log to stdout
        println!(
            "[MEMORY] Compiled intent '{}' into plan with {} nodes",
            intent.goal.raw_text,
            plan.nodes.len()
        );
    }

    pub fn summary(&self) -> String {
        let missions = self
            .nodes
            .iter()
            .filter(|n| n.kind == MemoryKind::Mission)
            .count();
        let playbooks = self
            .nodes
            .iter()
            .filter(|n| n.kind == MemoryKind::Playbook)
            .count();
        format!("Missions: {}, Playbooks: {}", missions, playbooks)
    }
}
