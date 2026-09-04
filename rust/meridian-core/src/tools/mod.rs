// src/tools/mod.rs
use serde_json::Value;
use std::collections::HashMap;
use thiserror::Error;
use async_trait::async_trait;

#[derive(Error, Debug)]
pub enum ToolError {
    #[error("Tool not found: {0}")]
    NotFound(String),
    #[error("Invalid arguments: {0}")]
    InvalidArgs(String),
    #[error("Execution failed: {0}")]
    ExecutionFailed(String),
}

#[derive(Debug, Clone)]
pub struct ToolCall {
    pub name: String,
    pub arguments: Value,
}

#[derive(Debug, Clone)]
pub struct ToolResult {
    pub name: String,
    pub output: String,
}

/// Trait for implementing tools
#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    fn schema(&self) -> Value;  // JSON Schema
    async fn execute(&self, args: Value) -> Result<String, ToolError>;
}

/// Registry of all available tools
pub struct ToolRegistry {
    tools: HashMap<String, Box<dyn Tool>>,
    schemas: HashMap<String, Value>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
            schemas: HashMap::new(),
        }
    }

    pub fn register(&mut self, tool: Box<dyn Tool>) {
        let name = tool.name().to_string();
        let schema = tool.schema();
        self.schemas.insert(name.clone(), schema);
        self.tools.insert(name, tool);
    }

    pub async fn execute(&self, name: &str, args: Value) -> Result<String, ToolError> {
        let tool = self.tools.get(name)
            .ok_or_else(|| ToolError::NotFound(name.to_string()))?;
        tool.execute(args).await
    }

    pub fn get_schemas_for(&self, tool_names: &[String]) -> Vec<Value> {
        tool_names.iter()
            .filter_map(|name| self.schemas.get(name).cloned())
            .collect()
    }

    pub fn list_tools(&self) -> Vec<&str> {
        self.tools.keys().map(|s| s.as_str()).collect()
    }
}

impl Default for ToolRegistry {
    fn default() -> Self {
        Self::new()
    }
}

// ─── Built-in Tools ──────────────────────────────────────────

pub struct WebSearchTool;

#[async_trait]
impl Tool for WebSearchTool {
    fn name(&self) -> &str { "web_search" }
    fn description(&self) -> &str { "Search the web using DuckDuckGo" }

    fn schema(&self) -> Value {
        serde_json::json!({
            "name": "web_search",
            "description": "Search the web using DuckDuckGo",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": { "type": "string", "description": "Search query" }
                },
                "required": ["query"]
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<String, ToolError> {
        let query = args["query"].as_str()
            .ok_or(ToolError::InvalidArgs("Missing 'query'".to_string()))?;

        // TODO: Actual DuckDuckGo search implementation
        Ok(format!("Search results for '{}': [Mock results]", query))
    }
}

pub struct FileReadTool;

#[async_trait]
impl Tool for FileReadTool {
    fn name(&self) -> &str { "file_read" }
    fn description(&self) -> &str { "Read contents of a file" }

    fn schema(&self) -> Value {
        serde_json::json!({
            "name": "file_read",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": { "type": "string", "description": "File path" }
                },
                "required": ["path"]
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<String, ToolError> {
        let path = args["path"].as_str()
            .ok_or(ToolError::InvalidArgs("Missing 'path'".to_string()))?;

        tokio::fs::read_to_string(path)
            .await
            .map_err(|e| ToolError::ExecutionFailed(e.to_string()))
    }
}
