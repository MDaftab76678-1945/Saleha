use crate::types::*;
use serde_json::Value;
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::{mpsc, Mutex};
use tracing::{debug, error, info, warn};

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

pub struct AgentRuntime {
    pub agent: Agent,
    llm: Arc<Mutex<Box<dyn InferenceEngine>>>,
    tool_registry: Arc<ToolRegistry>,
    memory: Option<Arc<Mutex<MemoryManager>>>,
    tx: mpsc::Sender<AgentMessage>,
    _rx: Option<mpsc::Receiver<AgentMessage>>,
}

struct RunState {
    messages: Vec<ChatMessage>,
    iteration: u32,
    tool_results: Vec<ToolResult>,
}

impl AgentRuntime {
    pub fn new(
        agent: Agent,
        llm: Box<dyn InferenceEngine>,
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

    pub async fn run(&self, task: &str) -> Result<String, AgentError> {
        info!(agent = %self.agent.name, task = %task, "Starting agent run");

        let mut state = self.init_state(task).await?;
        let max_iter = self.agent.config.max_iterations;

        self.emit(AgentMessage::Thinking(format!(
            "[THINKING] {} is analyzing the task...",
            self.agent.name
        )))
        .await;

        for i in 0..max_iter {
            state.iteration = i;
            debug!(iteration = i, "Agent iteration started");

            let tool_schemas = self.tool_registry.get_schemas_for(&self.agent.tools);
            let llm_response = self.call_llm(&state.messages, &tool_schemas).await?;

            match llm_response {
                LLMResponse::Text(text) => {
                    info!("Agent returned final answer");
                    self.emit(AgentMessage::FinalAnswer(text.clone())).await;
                    self.save_to_memory(task, &text).await;
                    return Ok(text);
                }

                LLMResponse::ToolCall { name, arguments } => {
                    debug!(tool = %name, args = ?arguments, "Tool call requested");

                    self.emit(AgentMessage::ToolCall {
                        name: name.clone(),
                        args: arguments.clone(),
                    })
                    .await;

                    let result = self.execute_tool(&name, arguments).await?;

                    self.emit(AgentMessage::ToolResult {
                        name: name.clone(),
                        result: result.clone(),
                    })
                    .await;

                    state.messages.push(ChatMessage::assistant(format!(
                        "I will use the tool '{}' to help answer.",
                        name
                    )));
                    state.messages.push(ChatMessage::tool(&name, &result));
                    state.tool_results.push(ToolResult {
                        name,
                        output: result,
                    });
                }

                LLMResponse::Error(e) => {
                    error!(error = %e, "LLM returned error");
                    return Err(AgentError::InferenceError(e));
                }
            }
        }

        warn!(max = max_iter, "Max iterations reached");
        self.emit(AgentMessage::Error(format!(
            "Max iterations ({}) reached",
            max_iter
        )))
        .await;

        Err(AgentError::MaxIterationsReached(max_iter))
    }

    pub async fn run_streaming(
        &self,
        task: &str,
    ) -> Result<mpsc::Receiver<AgentMessage>, AgentError> {
        let (tx, rx) = mpsc::channel(128);

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

    async fn init_state(&self, task: &str) -> Result<RunState, AgentError> {
        let mut messages = Vec::new();
        messages.push(ChatMessage::system(&self.agent.system_prompt));

        if self.agent.memory_enabled {
            if let Some(mem) = &self.memory {
                let mem_guard = mem.lock().await;
                let relevant = mem_guard
                    .retrieve_relevant(task, 3)
                    .await
                    .map_err(AgentError::MemoryError)?;

                if !relevant.is_empty() {
                    let memory_context = relevant
                        .iter()
                        .map(|r| format!("- {}", r.content))
                        .collect::<Vec<_>>()
                        .join("\n");

                    messages.push(ChatMessage::system(&format!(
                        "Relevant context from memory:\n{}",
                        memory_context
                    )));
                }
            }
        }

        messages.push(ChatMessage::user(task));

        Ok(RunState {
            messages,
            iteration: 0,
            tool_results: Vec::new(),
        })
    }

    async fn call_llm(
        &self,
        messages: &[ChatMessage],
        tool_schemas: &[Value],
    ) -> Result<LLMResponse, AgentError> {
        let llm = self.llm.lock().await;
        llm.chat_with_tools(messages, tool_schemas, &self.agent.config)
            .await
            .map_err(AgentError::InferenceError)
    }

    async fn execute_tool(&self, name: &str, arguments: Value) -> Result<String, AgentError> {
        if !self.agent.tools.contains(&name.to_string()) {
            return Err(AgentError::InvalidToolCall(format!(
                "Tool '{}' not in agent's allowed tools: {:?}",
                name, self.agent.tools
            )));
        }

        let result = self
            .tool_registry
            .execute(name, arguments)
            .await
            .map_err(|e| AgentError::ToolError(format!("Tool '{}' failed: {}", name, e)))?;

        let max_len = 4000;
        let output = if result.len() > max_len {
            format!(
                "{}... [truncated, {} chars total]",
                &result[..max_len],
                result.len()
            )
        } else {
            result
        };

        Ok(output)
    }

    async fn save_to_memory(&self, task: &str, answer: &str) {
        if let Some(mem) = &self.memory {
            let mut mem_guard = mem.lock().await;
            let _ = mem_guard.save_interaction(task, answer).await;
        }
    }

    async fn emit(&self, msg: AgentMessage) {
        let _ = self.tx.send(msg).await;
    }
}

#[derive(Debug, Clone)]
pub enum AgentMessage {
    Thinking(String),
    ToolCall {
        name: String,
        args: Value,
    },
    ToolResult {
        name: String,
        result: String,
    },
    FinalAnswer(String),
    Error(String),
    Progress {
        step: u32,
        total: u32,
        description: String,
    },
}

pub struct AgentRuntimeBuilder {
    agent: Option<Agent>,
    llm: Option<Box<dyn InferenceEngine>>,
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

    pub fn llm(mut self, llm: Box<dyn InferenceEngine>) -> Self {
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

impl Default for AgentRuntimeBuilder {
    fn default() -> Self {
        Self::new()
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

#[cfg(test)]
mod tests {
    use super::*;
    use async_trait::async_trait;
    use serde_json::json;

    struct MockEchoTool;
    #[async_trait]
    impl Tool for MockEchoTool {
        fn name(&self) -> &str {
            "echo"
        }
        fn schema(&self) -> Value {
            json!({"name": "echo", "description": "Echo input"})
        }
        async fn execute(&self, args: Value) -> Result<String, String> {
            Ok(format!("Echoed: {}", args["msg"].as_str().unwrap_or("")))
        }
    }

    struct MockLLM {
        step: std::sync::atomic::AtomicU32,
    }

    #[async_trait]
    impl InferenceEngine for MockLLM {
        async fn chat_with_tools(
            &self,
            _messages: &[ChatMessage],
            _tool_schemas: &[Value],
            _config: &AgentConfig,
        ) -> Result<LLMResponse, String> {
            let s = self.step.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            if s == 0 {
                Ok(LLMResponse::ToolCall {
                    name: "echo".to_string(),
                    arguments: json!({"msg": "hello from tool"}),
                })
            } else {
                Ok(LLMResponse::Text(
                    "Task completed with tool output.".to_string(),
                ))
            }
        }
    }

    #[tokio::test]
    async fn test_agent_react_loop_with_tool() {
        let mut registry = ToolRegistry::new();
        registry.register(Arc::new(MockEchoTool));

        let agent = Agent {
            name: "TestAgent".to_string(),
            system_prompt: "You are a test agent.".to_string(),
            tools: vec!["echo".to_string()],
            memory_enabled: true,
            config: AgentConfig::default(),
        };

        let llm = Box::new(MockLLM {
            step: std::sync::atomic::AtomicU32::new(0),
        });

        let (runtime, mut rx) = AgentRuntimeBuilder::new()
            .agent(agent)
            .llm(llm)
            .tools(registry)
            .memory(MemoryManager::new())
            .build()
            .expect("build runtime");

        let result = runtime.run("do the echo task").await.expect("agent run");
        assert_eq!(result, "Task completed with tool output.");

        // Verify emitted stream
        let mut messages = Vec::new();
        while let Ok(msg) = rx.try_recv() {
            messages.push(msg);
        }
        assert!(!messages.is_empty());
    }
}
