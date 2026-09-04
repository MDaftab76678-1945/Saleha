
# 2. SWARM ORCHESTRATION — Multi-agent orchestrator

swarm_rs = '''// src/agent/swarm.rs
// MERIDIAN — Multi-Agent Swarm Orchestrator
// Agents collaborate via message bus. Coordinator decomposes tasks.

use super::{Agent, AgentRuntime, AgentMessage, AgentError};
use crate::llm::{InferenceEngine, LLMError};
use crate::tools::ToolRegistry;
use crate::memory::MemoryManager;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::{mpsc, broadcast, RwLock};
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{info, debug, warn, error};
use uuid::Uuid;

// ═══════════════════════════════════════════════════════════════
// Swarm-Level Types
// ═══════════════════════════════════════════════════════════════

#[derive(Error, Debug, Clone)]
pub enum SwarmError {
    #[error("Agent error: {0}")]
    AgentError(String),
    
    #[error("Coordinator failed: {0}")]
    CoordinatorError(String),
    
    #[error("Task decomposition failed: {0}")]
    DecompositionError(String),
    
    #[error("All agents failed")]
    AllAgentsFailed,
    
    #[error("Timeout after {0}s")]
    Timeout(u64),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwarmTask {
    pub id: String,
    pub description: String,
    pub sub_tasks: Vec<SubTask>,
    pub priority: TaskPriority,
    pub timeout_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubTask {
    pub id: String,
    pub description: String,
    pub assigned_agent: String,
    pub dependencies: Vec<String>, // SubTask IDs that must complete first
    pub tools: Vec<String>,
    pub expected_output: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TaskPriority {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone)]
pub struct SwarmResult {
    pub task_id: String,
    pub status: SwarmStatus,
    pub agent_results: HashMap<String, AgentResult>,
    pub merged_output: String,
    pub execution_time_ms: u64,
}

#[derive(Debug, Clone)]
pub struct AgentResult {
    pub agent_name: String,
    pub sub_task_id: String,
    pub output: String,
    pub tokens_used: u32,
    pub tool_calls: u32,
    pub execution_time_ms: u64,
    pub status: AgentResultStatus,
}

#[derive(Debug, Clone)]
pub enum AgentResultStatus {
    Success,
    PartialSuccess(String), // With warning
    Failed(String),
    Skipped, // Dependency failed
}

#[derive(Debug, Clone)]
pub enum SwarmStatus {
    Success,
    PartialSuccess,
    Failed,
}

// ═══════════════════════════════════════════════════════════════
// Inter-Agent Message Bus
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone)]
pub enum SwarmMessage {
    TaskAssigned {
        sub_task_id: String,
        agent_name: String,
        description: String,
    },
    AgentProgress {
        agent_name: String,
        sub_task_id: String,
        message: String,
        percent: u8,
    },
    AgentCompleted {
        agent_name: String,
        sub_task_id: String,
        result: String,
    },
    AgentFailed {
        agent_name: String,
        sub_task_id: String,
        error: String,
    },
    Question {
        from: String,
        to: String,
        question: String,
    },
    Answer {
        from: String,
        to: String,
        answer: String,
    },
    Broadcast {
        from: String,
        content: String,
    },
}

/// Thread-safe message bus for swarm communication
pub struct SwarmBus {
    tx: broadcast::Sender<SwarmMessage>,
}

impl SwarmBus {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(256);
        Self { tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<SwarmMessage> {
        self.tx.subscribe()
    }

    pub fn send(&self, msg: SwarmMessage) {
        let _ = self.tx.send(msg);
    }
}

impl Default for SwarmBus {
    fn default() -> Self {
        Self::new()
    }
}

// ═══════════════════════════════════════════════════════════════
// Swarm Orchestrator
// ═══════════════════════════════════════════════════════════════

pub struct SwarmOrchestrator {
    agents: HashMap<String, AgentRuntimeHandle>,
    bus: Arc<SwarmBus>,
    coordinator: Option<Agent>,
    llm: Arc<RwLock<InferenceEngine>>,
    tools: Arc<ToolRegistry>,
    memory: Option<Arc<RwLock<MemoryManager>>>,
}

/// Handle to an agent runtime (cloneable reference)
#[derive(Clone)]
struct AgentRuntimeHandle {
    agent: Agent,
    tx: mpsc::Sender<AgentMessage>,
}

impl SwarmOrchestrator {
    pub fn new(
        llm: InferenceEngine,
        tools: ToolRegistry,
        memory: Option<MemoryManager>,
    ) -> Self {
        Self {
            agents: HashMap::new(),
            bus: Arc::new(SwarmBus::new()),
            coordinator: None,
            llm: Arc::new(RwLock::new(llm)),
            tools: Arc::new(tools),
            memory: memory.map(|m| Arc::new(RwLock::new(m))),
        }
    }

    /// Register an agent into the swarm
    pub fn register_agent(&mut self, agent: Agent) -> Result<(), SwarmError> {
        let (tx, _rx) = mpsc::channel(128);
        
        self.agents.insert(
            agent.name.clone(),
            AgentRuntimeHandle { agent: agent.clone(), tx },
        );
        
        info!(agent = %agent.name, tools = ?agent.tools, "Agent registered in swarm");
        Ok(())
    }

    /// Set a coordinator agent (optional — decomposes complex tasks)
    pub fn set_coordinator(&mut self, agent: Agent) {
        self.coordinator = Some(agent);
        info!("Coordinator agent set");
    }

    // ───────────────────────────────────────────────────────────
    // MAIN: Execute a task with the swarm
    // ───────────────────────────────────────────────────────────
    
    pub async fn execute(&self, task_description: &str) -> Result<SwarmResult, SwarmError> {
        let start = std::time::Instant::now();
        let task_id = Uuid::new_v4().to_string();
        
        info!(task_id = %task_id, "🐝 Swarm execution started");

        // Phase 1: Decompose task into sub-tasks
        let swarm_task = self.decompose_task(task_description).await?;
        
        // Phase 2: Build execution DAG from dependencies
        let execution_plan = self.build_execution_plan(&swarm_task)?;
        
        // Phase 3: Execute sub-tasks (parallel where possible)
        let agent_results = self.execute_plan(&execution_plan, &swarm_task).await?;
        
        // Phase 4: Merge results
        let merged = self.merge_results(&agent_results, task_description).await?;
        
        let elapsed = start.elapsed().as_millis() as u64;
        
        let status = if agent_results.values().all(|r| matches!(r.status, AgentResultStatus::Success)) {
            SwarmStatus::Success
        } else if agent_results.values().any(|r| matches!(r.status, AgentResultStatus::Success)) {
            SwarmStatus::PartialSuccess
        } else {
            SwarmStatus::Failed
        };

        info!(task_id = %task_id, status = ?status, time_ms = elapsed, "Swarm execution complete");

        Ok(SwarmResult {
            task_id,
            status,
            agent_results,
            merged_output: merged,
            execution_time_ms: elapsed,
        })
    }

    // ─── PHASE 1: Task Decomposition ──────────────────────────

    async fn decompose_task(&self, task: &str) -> Result<SwarmTask, SwarmError> {
        // If no coordinator, create a single sub-task
        if self.coordinator.is_none() {
            return Ok(SwarmTask {
                id: Uuid::new_v4().to_string(),
                description: task.to_string(),
                sub_tasks: vec![SubTask {
                    id: "task_0".to_string(),
                    description: task.to_string(),
                    assigned_agent: self.get_default_agent(),
                    dependencies: vec![],
                    tools: vec![],
                    expected_output: "Complete solution".to_string(),
                }],
                priority: TaskPriority::Medium,
                timeout_secs: 300,
            });
        }

        // Use coordinator to decompose
        let coord = self.coordinator.as_ref().unwrap();
        let coord_prompt = format!(
            "You are a task coordinator. Break down this complex task into 2-5 sub-tasks. \\n\\n"
            "Available agents: {}\\n"
            "Task: {}\\n\\n"
            "Respond in JSON format:\\n"
            '{{"sub_tasks": [\\n'
            '  {{"id": "task_1", "description": "...", "assigned_agent": "agent_name", "dependencies": [], "tools": ["tool1"], "expected_output": "..."}}\\n'
            ']}}',
            self.agents.keys().cloned().collect::<Vec<_>>().join(", "),
            task
        );

        // Mock decomposition for now
        let sub_tasks = vec![
            SubTask {
                id: "research".to_string(),
                description: format!("Research: {}", task),
                assigned_agent: self.find_agent_with_capability("research"),
                dependencies: vec![],
                tools: vec!["web_search".to_string(), "arxiv_search".to_string()],
                expected_output: "Research summary with sources".to_string(),
            },
            SubTask {
                id: "implement".to_string(),
                description: format!("Implement solution for: {}", task),
                assigned_agent: self.find_agent_with_capability("code"),
                dependencies: vec!["research".to_string()],
                tools: vec!["code_write".to_string(), "code_exec".to_string()],
                expected_output: "Working code".to_string(),
            },
            SubTask {
                id: "document".to_string(),
                description: "Write documentation".n                assigned_agent: self.find_agent_with_capability("write"),
                dependencies: vec!["implement".to_string()],
                tools: vec!["markdown_write".to_string()],
                expected_output: "README and docs".to_string(),
            },
        ];

        Ok(SwarmTask {
            id: Uuid::new_v4().to_string(),
            description: task.to_string(),
            sub_tasks,
            priority: TaskPriority::Medium,
            timeout_secs: 300,
        })
    }

    // ─── PHASE 2: Build Execution DAG ─────────────────────────

    fn build_execution_plan(&self, task: &SwarmTask) -> Result<Vec<Vec<String>>, SwarmError> {
        let mut plan: Vec<Vec<String>> = Vec::new();
        let mut completed = std::collections::HashSet::new();
        let mut remaining: Vec<_> = task.sub_tasks.iter().map(|s| &s.id).collect();

        while !remaining.is_empty() {
            let mut batch = Vec::new();
            let mut still_remaining = Vec::new();

            for sub_task_id in remaining {
                let sub_task = task.sub_tasks.iter()
                    .find(|s| &s.id == sub_task_id)
                    .ok_or_else(|| SwarmError::DecompositionError(
                        format!("Sub-task {} not found", sub_task_id)
                    ))?;

                // Check if all dependencies are completed
                let deps_satisfied = sub_task.dependencies.iter()
                    .all(|dep| completed.contains(dep));

                if deps_satisfied {
                    batch.push(sub_task_id.clone());
                } else {
                    still_remaining.push(sub_task_id.clone());
                }
            }

            if batch.is_empty() && !still_remaining.is_empty() {
                return Err(SwarmError::DecompositionError(
                    "Circular dependency detected in sub-tasks".to_string()
                ));
            }

            for id in &batch {
                completed.insert(id.clone());
            }
            plan.push(batch);
            remaining = still_remaining;
        }

        info!(plan = ?plan, "Execution plan built");
        Ok(plan)
    }

    // ─── PHASE 3: Execute Plan ────────────────────────────────

    async fn execute_plan(
        &self,
        plan: &[Vec<String>],
        task: &SwarmTask,
    ) -> Result<HashMap<String, AgentResult>, SwarmError> {
        let mut all_results = HashMap::new();
        let mut previous_outputs: HashMap<String, String> = HashMap::new();

        for (batch_idx, batch) in plan.iter().enumerate() {
            info!(batch = batch_idx + 1, total = plan.len(), tasks = ?batch, "Executing batch");

            // Execute all sub-tasks in this batch in parallel
            let mut handles = Vec::new();

            for sub_task_id in batch {
                let sub_task = task.sub_tasks.iter()
                    .find(|s| &s.id == sub_task_id)
                    .unwrap()
                    .clone();

                let agent_name = sub_task.assigned_agent.clone();
                let handle = self.spawn_agent_task(
                    sub_task,
                    previous_outputs.clone(),
                );
                handles.push((agent_name, sub_task_id.clone(), handle));
            }

            // Wait for all parallel tasks
            for (agent_name, sub_task_id, handle) in handles {
                match handle.await {
                    Ok(Ok(result)) => {
                        previous_outputs.insert(sub_task_id.clone(), result.output.clone());
                        all_results.insert(sub_task_id, result);
                    }
                    Ok(Err(e)) => {
                        warn!(agent = %agent_name, error = %e, "Agent task failed");
                        all_results.insert(sub_task_id.clone(), AgentResult {
                            agent_name,
                            sub_task_id: sub_task_id.clone(),
                            output: String::new(),
                            tokens_used: 0,
                            tool_calls: 0,
                            execution_time_ms: 0,
                            status: AgentResultStatus::Failed(e.to_string()),
                        });
                    }
                    Err(e) => {
                        error!("Task join error: {}", e);
                        all_results.insert(sub_task_id.clone(), AgentResult {
                            agent_name,
                            sub_task_id: sub_task_id.clone(),
                            output: String::new(),
                            tokens_used: 0,
                            tool_calls: 0,
                            execution_time_ms: 0,
                            status: AgentResultStatus::Failed("Join error".to_string()),
                        });
                    }
                }
            }
        }

        Ok(all_results)
    }

    fn spawn_agent_task(
        &self,
        sub_task: SubTask,
        context: HashMap<String, String>,
    ) -> tokio::task::JoinHandle<Result<AgentResult, AgentError>> {
        let agent_handle = self.agents.get(&sub_task.assigned_agent).cloned();
        let llm = self.llm.clone();
        let tools = self.tools.clone();
        let memory = self.memory.clone();
        let bus = self.bus.clone();
        let sub_task_id = sub_task.id.clone();
        let agent_name = sub_task.assigned_agent.clone();

        tokio::spawn(async move {
            let start = std::time::Instant::now();
            
            let Some(handle) = agent_handle else {
                return Err(AgentError::InferenceError(format!(
                    "Agent '{}' not found in swarm", agent_name
                )));
            };

            // Build task prompt with context from previous steps
            let mut task_prompt = sub_task.description.clone();
            if !context.is_empty() {
                task_prompt.push_str("\\n\\nContext from previous steps:\\n");
                for (dep_id, output) in &context {
                    task_prompt.push_str(&format!("- {}: {}\\n", dep_id, 
                        if output.len() > 200 { &output[..200] } else { output }));
                }
            }

            // Create runtime and run
            let agent = handle.agent.clone();
            let (runtime, mut rx) = AgentRuntime::new(
                agent.clone(),
                llm.read().await.clone(),
                tools.as_ref().clone(),
                memory.as_ref().map(|m| m.read().await.clone()),
            );

            // Forward agent messages to swarm bus
            let bus_clone = bus.clone();
            let agent_name_clone = agent_name.clone();
            let sub_task_id_clone = sub_task_id.clone();
            tokio::spawn(async move {
                while let Some(msg) = rx.recv().await {
                    let swarm_msg = match msg {
                        AgentMessage::Thinking(t) => SwarmMessage::AgentProgress {
                            agent_name: agent_name_clone.clone(),
                            sub_task_id: sub_task_id_clone.clone(),
                            message: t,
                            percent: 25,
                        },
                        AgentMessage::ToolCall { name, .. } => SwarmMessage::AgentProgress {
                            agent_name: agent_name_clone.clone(),
                            sub_task_id: sub_task_id_clone.clone(),
                            message: format!("Using tool: {}", name),
                            percent: 50,
                        },
                        AgentMessage::FinalAnswer(_) => SwarmMessage::AgentCompleted {
                            agent_name: agent_name_clone.clone(),
                            sub_task_id: sub_task_id_clone.clone(),
                            result: "Complete".to_string(),
                        },
                        AgentMessage::Error(e) => SwarmMessage::AgentFailed {
                            agent_name: agent_name_clone.clone(),
                            sub_task_id: sub_task_id_clone.clone(),
                            error: e,
                        },
                        _ => continue,
                    };
                    bus_clone.send(swarm_msg);
                }
            });

            let output = runtime.run(&task_prompt).await?;
            let elapsed = start.elapsed().as_millis() as u64;

            Ok(AgentResult {
                agent_name: agent_name.clone(),
                sub_task_id: sub_task_id.clone(),
                output,
                tokens_used: 0, // TODO: track from runtime
                tool_calls: 0,  // TODO: track from runtime
                execution_time_ms: elapsed,
                status: AgentResultStatus::Success,
            })
        })
    }

    // ─── PHASE 4: Merge Results ───────────────────────────────

    async fn merge_results(
        &self,
        results: &HashMap<String, AgentResult>,
        original_task: &str,
    ) -> Result<String, SwarmError> {
        // If only one result, return it directly
        if results.len() == 1 {
            return Ok(results.values().next().unwrap().output.clone());
        }

        // Otherwise, use coordinator or first agent to synthesize
        let mut combined = format!(
            "Original task: {}\\n\\nResults from swarm agents:\\n\\n",
            original_task
        );

        for (id, result) in results {
            combined.push_str(&format!(
                "## {} (by {})\\n{}\\n\\n",
                id, result.agent_name, result.output
            ));
        }

        // If coordinator exists, ask it to synthesize
        if let Some(coord) = &self.coordinator {
            let synthesize_prompt = format!(
                "You are a coordinator. Synthesize these agent outputs into a single coherent response.\\n\\n{}",
                combined
            );
            
            // For now, return combined output
            return Ok(combined);
        }

        Ok(combined)
    }

    // ─── HELPERS ──────────────────────────────────────────────

    fn get_default_agent(&self) -> String {
        self.agents.keys().next().cloned()
            .unwrap_or_else(|| "default".to_string())
    }

    fn find_agent_with_capability(&self, capability: &str) -> String {
        // Simple heuristic: match agent name to capability
        for (name, handle) in &self.agents {
            let agent = &handle.agent;
            if agent.name.contains(capability) 
                || agent.description.to_lowercase().contains(capability) {
                return name.clone();
            }
            // Check tools
            for tool in &agent.tools {
                if tool.contains(capability) {
                    return name.clone();
                }
            }
        }
        self.get_default_agent()
    }

    /// Subscribe to swarm events (for GUI/CLI streaming)
    pub fn subscribe_events(&self) -> broadcast::Receiver<SwarmMessage> {
        self.bus.subscribe()
    }
}

// ═══════════════════════════════════════════════════════════════
// Builder for easy setup
// ═══════════════════════════════════════════════════════════════

pub struct SwarmBuilder {
    agents: Vec<Agent>,
    coordinator: Option<Agent>,
    llm: Option<InferenceEngine>,
    tools: Option<ToolRegistry>,
    memory: Option<MemoryManager>,
}

impl SwarmBuilder {
    pub fn new() -> Self {
        Self {
            agents: Vec::new(),
            coordinator: None,
            llm: None,
            tools: None,
            memory: None,
        }
    }

    pub fn with_agent(mut self, agent: Agent) -> Self {
        self.agents.push(agent);
        self
    }

    pub fn with_coordinator(mut self, agent: Agent) -> Self {
        self.coordinator = Some(agent);
        self
    }

    pub fn with_llm(mut self, llm: InferenceEngine) -> Self {
        self.llm = Some(llm);
        self
    }

    pub fn with_tools(mut self, tools: ToolRegistry) -> Self {
        self.tools = Some(tools);
        self
    }

    pub fn with_memory(mut self, memory: MemoryManager) -> Self {
        self.memory = Some(memory);
        self
    }

    pub fn build(self) -> Result<SwarmOrchestrator, SwarmError> {
        let llm = self.llm.ok_or_else(|| SwarmError::AgentError(
            "LLM engine required".to_string()
        ))?;
        let tools = self.tools.ok_or_else(|| SwarmError::AgentError(
            "Tool registry required".to_string()
        ))?;

        let mut swarm = SwarmOrchestrator::new(llm, tools, self.memory);

        if let Some(coord) = self.coordinator {
            swarm.set_coordinator(coord);
        }

        for agent in self.agents {
            swarm.register_agent(agent)?;
        }

        Ok(swarm)
    }
}

impl Default for SwarmBuilder {
    fn default() -> Self {
        Self::new()
    }
}
'''

with open('/mnt/agents/output/meridian-core/src/agent/swarm.rs', 'w') as f:
    f.write(swarm_rs)
print("✅ src/agent/swarm.rs")
