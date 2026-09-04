// examples/agent_demo.rs
// Run with: cargo run --example agent_demo

use meridian_core::{
    agent::{Agent, AgentConfig, AgentMessage, AgentRuntimeBuilder},
    llm::InferenceEngine,
    tools::{ToolRegistry, WebSearchTool, FileReadTool},
    memory::MemoryManager,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Create an agent
    let researcher = Agent::new(
        "researcher",
        "You are a research assistant. Use web_search and file_read tools to gather information."
    )
    .with_model("mistral-7b-instruct-v0.2.Q4_K_M.gguf")
    .with_tools(vec!["web_search", "file_read"]);

    // 2. Set up LLM engine
    let llm = InferenceEngine::new(
        "~/.meridian/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        35, // GPU layers
    );

    // 3. Set up tools
    let mut registry = ToolRegistry::new();
    registry.register(Box::new(WebSearchTool));
    registry.register(Box::new(FileReadTool));

    // 4. Set up memory (optional)
    let memory = MemoryManager::new("~/.meridian/memory.db")?;

    // 5. Build runtime
    let (runtime, mut rx) = AgentRuntimeBuilder::new()
        .agent(researcher)
        .llm(llm)
        .tools(registry)
        .memory(memory)
        .build()?;

    // 6. Stream progress in background
    tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            match msg {
                AgentMessage::Thinking(t) => println!("🤔 {}", t),
                AgentMessage::ToolCall { name, args } => {
                    println!("🔧 Calling tool: {} with args: {}", name, args);
                }
                AgentMessage::ToolResult { name, result } => {
                    println!("✅ Tool {} returned: {}", name, 
                        if result.len() > 100 { &result[..100] } else { &result });
                }
                AgentMessage::FinalAnswer(a) => println!("🎯 Final Answer: {}", a),
                AgentMessage::Error(e) => eprintln!("❌ Error: {}", e),
                _ => {}
            }
        }
    });

    // 7. Run the agent
    let result = runtime.run("Research the latest trends in local LLMs").await?;
    println!("\n📄 Result: {}", result);

    Ok(())
}
