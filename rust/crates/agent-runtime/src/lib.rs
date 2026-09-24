//! agent-runtime crate
//! Sovereign ReAct Agent Execution Runtime with tool calling, memory, and streaming.

#![allow(dead_code)]

pub mod runtime;
pub mod types;

pub use runtime::{AgentBuildError, AgentError, AgentMessage, AgentRuntime, AgentRuntimeBuilder};
pub use types::{
    Agent, AgentConfig, ChatMessage, InferenceEngine, LLMResponse, MemoryItem, MemoryManager, Tool,
    ToolRegistry, ToolResult,
};
