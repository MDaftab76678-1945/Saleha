use serde_json::{json, Value};
use tokio::process::{Command, ChildStdin, ChildStdout};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use std::collections::HashMap;

/// MCP (Model Context Protocol) Client
/// Connects to external MCP servers via stdio or HTTP
pub struct McpClient {
    server_name: String,
    process: Option<tokio::process::Child>,
    stdin: Option<ChildStdin>,
    reader: Option<BufReader<ChildStdout>>,
    tools: Vec<McpTool>,
}

#[derive(Debug, Clone)]
pub struct McpTool {
    pub name: String,
    pub description: String,
    pub input_schema: Value,  // JSON Schema
}

impl McpClient {
    /// Spawn an MCP server (e.g., npx @modelcontextprotocol/server-filesystem)
    pub async fn spawn_stdio(name: &str, command: &str, args: &[&str]) -> Result<Self, McpError> {
        let mut child = Command::new(command)
            .args(args)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .spawn()?;

        let stdin = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let reader = BufReader::new(stdout);

        let mut client = McpClient {
            server_name: name.to_string(),
            process: Some(child),
            stdin: Some(stdin),
            reader: Some(reader),
            tools: vec![],
        };

        // Initialize handshake
        client.initialize().await?;
        // Discover available tools
        client.discover_tools().await?;

        Ok(client)
    }

    /// MCP initialize handshake
    async fn initialize(&mut self) -> Result<(), McpError> {
        let request = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": { "name": "meridian", "version": "0.1.0" }
            }
        });
        self.send_request(&request).await?;
        let _ = self.read_response().await?; // Ack
        Ok(())
    }

    /// Discover tools from MCP server
    async fn discover_tools(&mut self) -> Result<(), McpError> {
        let request = json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        });
        self.send_request(&request).await?;
        let response = self.read_response().await?;

        if let Some(result) = response.get("result") {
            if let Some(tools) = result.get("tools") {
                self.tools = serde_json::from_value(tools.clone())?;
            }
        }
        Ok(())
    }

    /// Execute a tool via MCP
    pub async fn call_tool(&mut self, tool_name: &str, arguments: Value) -> Result<String, McpError> {
        let request = json!({
            "jsonrpc": "2.0",
            "id": uuid::Uuid::new_v4().to_string(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        });
        self.send_request(&request).await?;
        let response = self.read_response().await?;

        if let Some(result) = response.get("result") {
            if let Some(content) = result.get("content") {
                return Ok(content.to_string());
            }
        }
        Err(McpError::ToolExecutionFailed)
    }

    async fn send_request(&mut self, request: &Value) -> Result<(), McpError> {
        let json = request.to_string() + "\n";
        if let Some(stdin) = &mut self.stdin {
            stdin.write_all(json.as_bytes()).await?;
            stdin.flush().await?;
        }
        Ok(())
    }

    async fn read_response(&mut self) -> Result<Value, McpError> {
        if let Some(reader) = &mut self.reader {
            let mut line = String::new();
            reader.read_line(&mut line).await?;
            return Ok(serde_json::from_str(&line)?);
        }
        Err(McpError::ConnectionLost)
    }

    pub fn list_tools(&self) -> &[McpTool] {
        &self.tools
    }
}

// ─── Register MCP tools into MERIDIAN's ToolRegistry ───
pub async fn register_mcp_tools(registry: &mut ToolRegistry, mcp_clients: &mut [McpClient]) {
    for client in mcp_clients {
        for tool in client.list_tools() {
            let mcp_tool = McpToolWrapper {
                client_name: client.server_name.clone(),
                tool_name: tool.name.clone(),
            };
            registry.register(
                &tool.name,
                &tool.description,
                tool.input_schema.clone(),
                Box::new(mcp_tool),
            );
        }
    }
}