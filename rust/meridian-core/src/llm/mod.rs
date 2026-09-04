// src/llm/mod.rs
pub mod bindings;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use crate::agent::AgentConfig;
use thiserror::Error;

#[derive(Error, Debug, Clone)]
pub enum LLMError {
    #[error("Model not found: {0}")]
    ModelNotFound(String),
    #[error("Inference failed: {0}")]
    InferenceFailed(String),
    #[error("Context too long")]
    ContextTooLong,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

impl ChatMessage {
    pub fn system(content: impl Into<String>) -> Self {
        Self { role: "system".to_string(), content: content.into() }
    }
    pub fn user(content: impl Into<String>) -> Self {
        Self { role: "user".to_string(), content: content.into() }
    }
    pub fn assistant(content: impl Into<String>) -> Self {
        Self { role: "assistant".to_string(), content: content.into() }
    }
    pub fn tool(name: &str, content: impl Into<String>) -> Self {
        Self { 
            role: "tool".to_string(), 
            content: format!("[Tool: {}] {}", name, content.into()) 
        }
    }
}

#[derive(Debug, Clone)]
pub enum LLMResponse {
    Text(String),
    ToolCall { name: String, arguments: Value },
    Error(String),
}

// Re-export for convenience
pub use bindings::{LlamaInferenceEngine, ModelManager, ModelInfo};

/// Legacy inference engine (backward compat)
pub struct InferenceEngine {
    pub model_path: String,
    pub gpu_layers: u32,
}

impl InferenceEngine {
    pub fn new(model_path: &str, gpu_layers: u32) -> Self {
        Self {
            model_path: model_path.to_string(),
            gpu_layers,
        }
    }

    pub async fn chat_with_tools(
        &self,
        messages: &[ChatMessage],
        tool_schemas: &[Value],
        config: &AgentConfig,
    ) -> Result<LLMResponse, LLMError> {
        // Delegate to real engine if available, else mock
        let engine = LlamaInferenceEngine::load(&self.model_path, self.gpu_layers).await?;
        engine.chat_with_tools(messages, tool_schemas, config).await
    }

    pub fn clone(&self) -> Self {
        Self {
            model_path: self.model_path.clone(),
            gpu_layers: self.gpu_layers,
        }
    }
}
