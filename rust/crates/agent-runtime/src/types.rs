use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
    pub name: Option<String>,
}

impl ChatMessage {
    pub fn system(content: &str) -> Self {
        Self {
            role: "system".to_string(),
            content: content.to_string(),
            name: None,
        }
    }

    pub fn user(content: &str) -> Self {
        Self {
            role: "user".to_string(),
            content: content.to_string(),
            name: None,
        }
    }

    pub fn assistant(content: String) -> Self {
        Self {
            role: "assistant".to_string(),
            content,
            name: None,
        }
    }

    pub fn tool(name: &str, result: &str) -> Self {
        Self {
            role: "tool".to_string(),
            content: result.to_string(),
            name: Some(name.to_string()),
        }
    }
}

#[derive(Debug, Clone)]
pub enum LLMResponse {
    Text(String),
    ToolCall { name: String, arguments: Value },
    Error(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    pub max_iterations: u32,
    pub temperature: f32,
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            max_iterations: 10,
            temperature: 0.7,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    pub name: String,
    pub system_prompt: String,
    pub tools: Vec<String>,
    pub memory_enabled: bool,
    pub config: AgentConfig,
}

#[derive(Debug, Clone)]
pub struct ToolResult {
    pub name: String,
    pub output: String,
}

#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    fn schema(&self) -> Value;
    async fn execute(&self, args: Value) -> Result<String, String>;
}

#[derive(Default)]
pub struct ToolRegistry {
    tools: HashMap<String, Arc<dyn Tool>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
        }
    }

    pub fn register(&mut self, tool: Arc<dyn Tool>) {
        self.tools.insert(tool.name().to_string(), tool);
    }

    pub fn get_schemas_for(&self, allowed: &[String]) -> Vec<Value> {
        allowed
            .iter()
            .filter_map(|name| self.tools.get(name).map(|t| t.schema()))
            .collect()
    }

    pub async fn execute(&self, name: &str, args: Value) -> Result<String, String> {
        let tool = self
            .tools
            .get(name)
            .ok_or_else(|| format!("Tool '{}' not found", name))?;
        tool.execute(args).await
    }
}

#[derive(Debug, Clone)]
pub struct MemoryItem {
    pub content: String,
}

#[derive(Default)]
pub struct MemoryManager {
    items: Vec<String>,
}

impl MemoryManager {
    pub fn new() -> Self {
        Self { items: Vec::new() }
    }

    pub async fn retrieve_relevant(&self, _query: &str, limit: usize) -> Result<Vec<MemoryItem>, String> {
        let res = self
            .items
            .iter()
            .rev()
            .take(limit)
            .map(|c| MemoryItem { content: c.clone() })
            .collect();
        Ok(res)
    }

    pub async fn save_interaction(&mut self, task: &str, answer: &str) -> Result<(), String> {
        self.items.push(format!("Task: {} => Answer: {}", task, answer));
        Ok(())
    }
}

#[async_trait]
pub trait InferenceEngine: Send + Sync {
    async fn chat_with_tools(
        &self,
        messages: &[ChatMessage],
        tool_schemas: &[Value],
        config: &AgentConfig,
    ) -> Result<LLMResponse, String>;
}
