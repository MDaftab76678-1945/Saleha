// examples/swarm_demo.rs
// Run with: cargo run --example swarm_demo

use meridian_core::{
    agent::{
        Agent, AgentConfig, SwarmBuilder, SwarmMessage,
        TaskPriority, SwarmOrchestrator,
    },
    llm::InferenceEngine,
    tools::{ToolRegistry, WebSearchTool, FileReadTool},
    memory::MemoryManager,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🐝 MERIDIAN Swarm Demo\n");

    // 1. Create specialized agents
    let researcher = Agent::new(
        "researcher",
        "You are a research specialist. Find information, papers, and sources."
    )
    .with_model("mistral-7b-instruct-v0.2.Q4_K_M.gguf")
    .with_tools(vec!["web_search", "file_read"]);

    let coder = Agent::new(
        "coder",
        "You are a senior developer. Write clean, tested code."
    )
    .with_model("codellama-7b-instruct.Q4_K_M.gguf")
    .with_tools(vec!["file_read", "code_write"]);

    let writer = Agent::new(
        "writer",
        "You are a technical writer. Create clear documentation."
    )
    .with_model("llama-3.1-8b-instruct.Q4_K_M.gguf")
    .with_tools(vec!["file_read", "markdown_write"]);

    let coordinator = Agent::new(
        "coordinator",
        "You are a project coordinator. Break down tasks and synthesize results."
    )
    .with_model("mistral-7b-instruct-v0.2.Q4_K_M.gguf")
    .with_config(AgentConfig {
        temperature: 0.3,
        max_tokens: 2048,
        top_p: 0.9,
        max_iterations: 5,
    });

    // 2. Set up shared resources
    let llm = InferenceEngine::new(
        "~/.meridian/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        35,
    );

    let mut tools = ToolRegistry::new();
    tools.register(Box::new(WebSearchTool));
    tools.register(Box::new(FileReadTool));

    let memory = MemoryManager::new("~/.meridian/memory.db")?;

    // 3. Build swarm
    let swarm = SwarmBuilder::new()
        .with_llm(llm)
        .with_tools(tools)
        .with_memory(memory)
        .with_coordinator(coordinator)
        .with_agent(researcher)
        .with_agent(coder)
        .with_agent(writer)
        .build()?;

    // 4. Subscribe to swarm events for real-time display
    let mut events = swarm.subscribe_events();
    tokio::spawn(async move {
        while let Ok(msg) = events.recv().await {
            match msg {
                SwarmMessage::TaskAssigned { agent_name, sub_task_id, .. } => {
                    println!("📋 Task '{}' assigned to {}", sub_task_id, agent_name);
                }
                SwarmMessage::AgentProgress { agent_name, message, percent, .. } => {
                    println!("  [{}] {}% — {}", agent_name, percent, message);
                }
                SwarmMessage::AgentCompleted { agent_name, sub_task_id, .. } => {
                    println!("  ✅ {} completed {}", agent_name, sub_task_id);
                }
                SwarmMessage::AgentFailed { agent_name, error, .. } => {
                    println!("  ❌ {} failed: {}", agent_name, error);
                }
                SwarmMessage::Question { from, to, question } => {
                    println!("  ❓ {} asks {}: {}", from, to, question);
                }
                _ => {}
            }
        }
    });

    // 5. Execute a complex task
    println!("🚀 Launching swarm task...\n");
    let result = swarm.execute(
        "Build a Python CLI tool that fetches weather data from an API and displays it beautifully"
    ).await?;

    println!("\n═══════════════════════════════════════");
    println!("🎯 SWARM RESULT");
    println!("═══════════════════════════════════════");
    println!("Status: {:?}", result.status);
    println!("Time: {}ms", result.execution_time_ms);
    println!("\nAgent Results:");
    for (id, res) in &result.agent_results {
        println!("  • {} ({}): {:?}", id, res.agent_name, res.status);
        println!("    Output preview: {}...", 
            if res.output.len() > 100 { &res.output[..100] } else { &res.output });
    }
    println!("\n📄 Merged Output:\n{}", result.merged_output);

    Ok(())
}
