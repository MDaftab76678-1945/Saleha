// src/lib.rs
// MERIDIAN — Agentic Local LLM Platform
// Core library exports

pub mod agent;
pub mod llm;
pub mod tools;
pub mod memory;

// Re-export commonly used types
pub use agent::{
    Agent, AgentConfig, AgentRuntime, AgentRuntimeBuilder,
    AgentMessage, SwarmOrchestrator, SwarmBuilder, SwarmResult,
    SwarmMessage, SwarmBus, SwarmTask, SubTask, TaskPriority,
};
pub use llm::{
    InferenceEngine, LlamaInferenceEngine, ModelManager, ModelInfo,
    ChatMessage, LLMResponse, LLMError,
};
pub use tools::{
    ToolRegistry, Tool, ToolCall, ToolResult, ToolError,
    WebSearchTool, FileReadTool,
};
pub use memory::{
    MemoryManager, MemoryEntry, MemoryError,
};

/// Initialize tracing and core systems
pub fn init() {
    tracing_subscriber::fmt::init();
}
