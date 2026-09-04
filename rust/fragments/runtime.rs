// src/agent/runtime.rs
// MERIDIAN — Agent Execution Runtime
// Full ReAct loop with tool calling, memory, and streaming

use crate::{
    llm::{InferenceEngine, LLMResponse, ChatMessage},
    memory::MemoryManager,
    tools::{ToolRegistry, ToolCall, ToolResult},
    agent::{Agent, AgentConfig, AgentMessage},
};
use serde_json::{json, Value};
use tokio::sync::mpsc;
use std::sync::Arc;
use tokio::sync::Mutex;
use thiserror::Error;
use tracing::{info, debug, warn, error};

// ═══════════════════════════════════════════════════════════════
// Errors
// ═══════════════════════════════════════════════════════════════

#[derive(Error, Debug, Clone)]
pub enum AgentError {
    #[error("LLM inference failed: {0}")]
    InferenceError(String),

    #[error("Tool execution failed: {0}")]
    ToolError(String),

    #[error("Max iterations ({0}) reached without final answer")]
    MaxIterationsReached(u32),

    #[error("Invalid tool call: {0}")]
    InvalidToolCall(String),

    #[error("Memory error: {0}")]
    MemoryError(String),

    #[error("Agent runtime cancelled")]
    Cancelled,
}

// ═══════════════════════════════════════════════════════════════
// Agent Runtime — The Heart of MERIDIAN
// ═══════════════════════════════════════════════════════════════

pub struct AgentRuntime {
    pub agent: Agent,
    llm: Arc<Mutex<InferenceEngine>>,
    tool_registry: Arc<ToolRegistry>,
    memory: Option<Arc<Mutex<MemoryManager>>>,
    tx: mpsc::Sender<AgentMessage>,
    _rx: Option<mpsc::Receiver<AgentMessage>>,
}

/// Internal state for one agent run
struct RunState {
    messages: Vec<ChatMessage>,
    iteration: u32,
    tool_results: Vec<ToolResult>,
}

impl AgentRuntime {
    /// Create a new runtime. Returns (runtime, receiver) for streaming.
    pub fn new(
        agent: Agent,
        llm: InferenceEngine,
        tool_registry: ToolRegistry,
        memory: Option<MemoryManager>,
    ) -> (Self, mpsc::Receiver<AgentMessage>) {
        let (tx, rx) = mpsc::channel::<AgentMessage>(128);

        let runtime = AgentRuntime {
            agent,
            llm: Arc::new(Mutex::new(llm)),
            tool_registry: Arc::new(tool_registry),
            memory: memory.map(|m| Arc::new(Mutex::new(m))),
            tx: tx.clone(),
            _rx: None,
        };

        (runtime, rx)
    }

    // ───────────────────────────────────────────────────────────
    // PUBLIC: Run the agent on a task
    // ───────────────────────────────────────────────────────────

    pub async fn run(&self, task: &str) -> Result<String, AgentError> {
        info!(agent = %self.agent.name, task = %task, "Starting agent run");

        let mut state = self.init_state(task).await?;
        let max_iter = self.agent.config.max_iterations;

        // Send "thinking" message
        self.emit(AgentMessage::Thinking(format!(
            "🤖 {} is analyzing the task...", self.agent.name
        ))).await;

        for i in 0..max_iter {
            state.iteration = i;
            debug!(iteration = i, "Agent iteration started");

            // 1. Build tool schemas for LLM
            let tool_schemas = self.tool_registry.get_schemas_for(&self.agent.tools);

            // 2. Call LLM with current context + available tools
            let llm_response = self.call_llm(&state.messages, &tool_schemas).await?;

            match llm_response {
                LLMResponse::Text(text) => {
                    // Agent gave final answer
                    info!("Agent returned final answer");
                    self.emit(AgentMessage::FinalAnswer(text.clone())).await;

                    // Save to long-term memory
                    self.save_to_memory(task, &text).await;

                    return Ok(text);
                }

                LLMResponse::ToolCall { name, arguments } => {
                    // Agent wants to use a tool
                    debug!(tool = %name, args = ?arguments, "Tool call requested");

                    self.emit(AgentMessage::ToolCall {
                        name: name.clone(),
                        args: arguments.clone(),
                    }).await;

                    // 3. Validate & execute the tool
                    let result = self.execute_tool(&name, arguments).await?;

                    self.emit(AgentMessage::ToolResult {
                        name: name.clone(),
                        result: result.clone(),
                    }).await;

                    // 4. Add tool result to conversation context
                    state.messages.push(ChatMessage::assistant(format!(
                        "I will use the tool '{}' to help answer.", name
                    )));
                    state.messages.push(ChatMessage::tool(&name, &result));
                    state.tool_results.push(ToolResult { name, output: result });
                }

                LLMResponse::Error(e) => {
                    error!(error = %e, "LLM returned error");
                    return Err(AgentError::InferenceError(e));
                }
            }
        }

        // Max iterations reached
        warn!(max = max_iter, "Max iterations reached");
        self.emit(AgentMessage::Error(format!(
            "Max iterations ({}) reached", max_iter
        ))).await;

        Err(AgentError::MaxIterationsReached(max_iter))
    }

    /// Run with streaming — returns receiver for real-time updates
    pub async fn run_streaming(
        &self,
        task: &str,
    ) -> Result<mpsc::Receiver<AgentMessage>, AgentError> {
        let (tx, rx) = mpsc::channel(128);

        // Clone what we need for the spawned task
        let task = task.to_string();
        let agent = self.agent.clone();
        let llm = self.llm.clone();
        let registry = self.tool_registry.clone();
        let memory = self.memory.clone();

        tokio::spawn(async move {
            let runtime = AgentRuntime {
                agent,
                llm,
                tool_registry: registry,
                memory,
                tx: tx.clone(),
                _rx: None,
            };

            match runtime.run(&task).await {
                Ok(answer) => {
                    let _ = tx.send(AgentMessage::FinalAnswer(answer)).await;
                }
                Err(e) => {
                    let _ = tx.send(AgentMessage::Error(e.to_string())).await;
                }
            }
        });

        Ok(rx)
    }

    // ───────────────────────────────────────────────────────────
    // INTERNAL: Initialize conversation state
    // ───────────────────────────────────────────────────────────

    async fn init_state(&self, task: &str) -> Result<RunState, AgentError> {
        let mut messages = Vec::new();

        // System prompt
        messages.push(ChatMessage::system(&self.agent.system_prompt));

        // Inject relevant memory if enabled
        if self.agent.memory_enabled {
            if let Some(mem) = &self.memory {
                let mem_guard = mem.lock().await;
                let relevant = mem_guard
                    .retrieve_relevant(task, 3)
                    .await
                    .map_err(|e| AgentError::MemoryError(e.to_string()))?;

                if !relevant.is_empty() {
                    let memory_context = relevant
                        .iter()
                        .map(|r| format!("- {}", r.content))
                        .collect::<Vec<_>>()
                        .join("\n");

                    messages.push(ChatMessage::system(format!(
                        "Relevant context from memory:\n{}", memory_context
                    )));
                }
            }
        }

        // User task
        messages.push(ChatMessage::user(task));

        Ok(RunState {
            messages,
            iteration: 0,
            tool_results: Vec::new(),
        })
    }

    // ───────────────────────────────────────────────────────────
    // INTERNAL: Call LLM with tool schemas
    // ───────────────────────────────────────────────────────────

    async fn call_llm(
        &self,
        messages: &[ChatMessage],
        tool_schemas: &[Value],
    ) -> Result<LLMResponse, AgentError> {
        let llm = self.llm.lock().await;

        let response = llm
            .chat_with_tools(messages, tool_schemas, &self.agent.config)
            .await
            .map_err(|e| AgentError::InferenceError(e.to_string()))?;

        Ok(response)
    }

    // ───────────────────────────────────────────────────────────
    // INTERNAL: Execute a tool
    // ───────────────────────────────────────────────────────────

    async fn execute_tool(
        &self,
        name: &str,
        arguments: Value,
    ) -> Result<String, AgentError> {
        // Validate tool is allowed for this agent
        if !self.agent.tools.contains(&name.to_string()) {
            return Err(AgentError::InvalidToolCall(format!(
                "Tool '{}' not in agent's allowed tools: {:?}",
                name, self.agent.tools
            )));
        }

        // Execute via registry
        let result = self.tool_registry
            .execute(name, arguments)
            .await
            .map_err(|e| AgentError::ToolError(format!(
                "Tool '{}' failed: {}", name, e
            )))?;

        // Truncate if too long (prevent context explosion)
        let max_len = 4000;
        let output = if result.len() > max_len {
            format!("{}... [truncated, {} chars total]", &result[..max_len], result.len())
        } else {
            result
        };

        Ok(output)
    }

    // ───────────────────────────────────────────────────────────
    // INTERNAL: Save interaction to memory
    // ───────────────────────────────────────────────────────────

    async fn save_to_memory(&self, task: &str, answer: &str) {
        if let Some(mem) = &self.memory {
            let mem_guard = mem.lock().await;
            let _ = mem_guard.save_interaction(task, answer).await;
        }
    }

    // ───────────────────────────────────────────────────────────
    // INTERNAL: Emit message to channel (non-blocking)
    // ───────────────────────────────────────────────────────────

    async fn emit(&self, msg: AgentMessage) {
        let _ = self.tx.send(msg).await;
    }
}

// ═══════════════════════════════════════════════════════════════
// Agent Message Types (for streaming)
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone)]
pub enum AgentMessage {
    Thinking(String),
    ToolCall { name: String, args: Value },
    ToolResult { name: String, result: String },
    FinalAnswer(String),
    Error(String),
    Progress { step: u32, total: u32, description: String },
}

// ═══════════════════════════════════════════════════════════════
// Builder Pattern for Easy Setup
// ═══════════════════════════════════════════════════════════════

pub struct AgentRuntimeBuilder {
    agent: Option<Agent>,
    llm: Option<InferenceEngine>,
    tools: Option<ToolRegistry>,
    memory: Option<MemoryManager>,
}

impl AgentRuntimeBuilder {
    pub fn new() -> Self {
        Self {
            agent: None,
            llm: None,
            tools: None,
            memory: None,
        }
    }

    pub fn agent(mut self, agent: Agent) -> Self {
        self.agent = Some(agent);
        self
    }

    pub fn llm(mut self, llm: InferenceEngine) -> Self {
        self.llm = Some(llm);
        self
    }

    pub fn tools(mut self, tools: ToolRegistry) -> Self {
        self.tools = Some(tools);
        self
    }

    pub fn memory(mut self, memory: MemoryManager) -> Self {
        self.memory = Some(memory);
        self
    }

    pub fn build(self) -> Result<(AgentRuntime, mpsc::Receiver<AgentMessage>), AgentBuildError> {
        let agent = self.agent.ok_or(AgentBuildError::MissingAgent)?;
        let llm = self.llm.ok_or(AgentBuildError::MissingLLM)?;
        let tools = self.tools.ok_or(AgentBuildError::MissingTools)?;

        Ok(AgentRuntime::new(agent, llm, tools, self.memory))
    }
}

#[derive(Error, Debug)]
pub enum AgentBuildError {
    #[error("Agent not provided")]
    MissingAgent,
    #[error("LLM engine not provided")]
    MissingLLM,
    #[error("Tool registry not provided")]
    MissingTools,
}
