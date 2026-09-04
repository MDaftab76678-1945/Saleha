
# 1. LLM BINDINGS — Real llama.cpp integration with FFI

llm_bindings_rs = '''// src/llm/bindings.rs
// MERIDIAN — Real llama.cpp FFI Bindings
// Uses llama-cpp-2 crate (modern Rust bindings)
// Falls back to mock mode if llama.cpp not compiled

use super::{ChatMessage, LLMError, LLMResponse, AgentConfig};
use serde_json::Value;
use std::path::Path;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{info, debug, warn, error};

// ═══════════════════════════════════════════════════════════════
// Feature-gated: real bindings vs mock
// ═══════════════════════════════════════════════════════════════

#[cfg(feature = "llama-cpp")]
mod real {
    pub use llama_cpp_2::context::params::LlamaContextParams;
    pub use llama_cpp_2::llama_backend::LlamaBackend;
    pub use llama_cpp_2::llama_batch::LlamaBatch;
    pub use llama_cpp_2::model::params::LlamaModelParams;
    pub use llama_cpp_2::model::LlamaModel;
    pub use llama_cpp_2::token::LlamaToken;
    pub use llama_cpp_2::ContextSize;
}

#[cfg(not(feature = "llama-cpp"))]
mod mock {
    // Mock types for compilation without llama.cpp
    pub struct LlamaBackend;
    impl LlamaBackend {
        pub fn init() -> Result<Self, String> { Ok(Self) }
    }
}

// ═══════════════════════════════════════════════════════════════
// Inference Engine with Real Bindings
// ═══════════════════════════════════════════════════════════════

pub struct LlamaInferenceEngine {
    model_path: String,
    gpu_layers: u32,
    context_size: u32,
    #[cfg(feature = "llama-cpp")]
    backend: Arc<real::LlamaBackend>,
    #[cfg(feature = "llama-cpp")]
    model: Arc<real::LlamaModel>,
}

impl LlamaInferenceEngine {
    /// Load a GGUF model from disk
    pub async fn load(model_path: &str, gpu_layers: u32) -> Result<Self, LLMError> {
        let path = Path::new(model_path);
        if !path.exists() {
            return Err(LLMError::ModelNotFound(format!(
                "Model not found at: {}", model_path
            )));
        }

        info!(path = %model_path, gpu_layers = gpu_layers, "Loading GGUF model");

        #[cfg(feature = "llama-cpp")]
        {
            let backend = Arc::new(
                real::LlamaBackend::init()
                    .map_err(|e| LLMError::InferenceFailed(format!(
                        "Backend init failed: {}", e
                    )))?
            );

            let model_params = real::LlamaModelParams::default()
                .with_n_gpu_layers(gpu_layers as i32);

            let model = Arc::new(
                real::LlamaModel::load_from_file(
                    &backend,
                    path,
                    &model_params,
                )
                .map_err(|e| LLMError::InferenceFailed(format!(
                    "Model load failed: {}", e
                )))?
            );

            info!(
                vocab_size = model.n_vocab(),
                context_size = model.n_ctx_train(),
                "Model loaded successfully"
            );

            Ok(Self {
                model_path: model_path.to_string(),
                gpu_layers,
                context_size: 4096,
                backend,
                model,
            })
        }

        #[cfg(not(feature = "llama-cpp"))]
        {
            warn!("llama-cpp feature not enabled — using mock inference");
            Ok(Self {
                model_path: model_path.to_string(),
                gpu_layers,
                context_size: 4096,
            })
        }
    }

    /// Main inference: chat with optional tool calling
    pub async fn chat_with_tools(
        &self,
        messages: &[ChatMessage],
        tool_schemas: &[Value],
        config: &AgentConfig,
    ) -> Result<LLMResponse, LLMError> {
        let prompt = self.build_prompt(messages, tool_schemas);
        
        #[cfg(feature = "llama-cpp")]
        {
            self.inference_real(&prompt, tool_schemas, config).await
        }

        #[cfg(not(feature = "llama-cpp"))]
        {
            self.inference_mock(&prompt, tool_schemas, config).await
        }
    }

    // ─── REAL INFERENCE (llama.cpp) ───────────────────────────

    #[cfg(feature = "llama-cpp")]
    async fn inference_real(
        &self,
        prompt: &str,
        tool_schemas: &[Value],
        config: &AgentConfig,
    ) -> Result<LLMResponse, LLMError> {
        use real::*;
        use llama_cpp_2::sampling::*;

        let ctx_params = LlamaContextParams::default()
            .with_n_ctx(Some(ContextSize::from_bytes(self.context_size as usize).unwrap()));

        let mut ctx = self.model
            .new_context(&self.backend, ctx_params)
            .map_err(|e| LLMError::InferenceFailed(e.to_string()))?;

        // Tokenize prompt
        let tokens_list = self.model
            .str_to_token(&prompt, llama_cpp_2::model::AddBos::Always)
            .map_err(|e| LLMError::InferenceFailed(format!("Tokenization failed: {}", e)))?;

        let n_tokens = tokens_list.len() as i32;
        debug!(n_tokens = n_tokens, "Prompt tokenized");

        // Check context limit
        if n_tokens > self.context_size as i32 {
            return Err(LLMError::ContextTooLong);
        }

        // Create batch
        let mut batch = LlamaBatch::new(self.model.n_ctx_train(), 1);
        let last_index: i32 = n_tokens - 1;

        for (i, token) in tokens_list.iter().enumerate() {
            batch.add(*token, i as i32, &[0], i == last_index as usize)
                .map_err(|e| LLMError::InferenceFailed(e.to_string()))?;
        }

        // Decode
        ctx.decode(&mut batch)
            .map_err(|e| LLMError::InferenceFailed(format!("Decode failed: {}", e)))?;

        // Sampling parameters
        let mut sampler = SamplerChain::new();
        sampler.push_sample_temperature(config.temperature);
        sampler.push_sampler_top_p(config.top_p);
        sampler.push_sampler_greedy();

        // Generate tokens
        let mut output_tokens = Vec::new();
        let max_tokens = config.max_tokens as usize;
        let mut n_cur = batch.n_tokens();

        for _ in 0..max_tokens {
            let token = sampler.sample(&ctx, -1);
            sampler.accept(token);

            if token == self.model.token_eos() {
                break;
            }

            output_tokens.push(token);
            batch.clear();
            batch.add(token, n_cur, &[0], true)
                .map_err(|e| LLMError::InferenceFailed(e.to_string()))?;
            
            ctx.decode(&mut batch)
                .map_err(|e| LLMError::InferenceFailed(format!("Decode failed: {}", e)))?;
            
            n_cur += 1;
        }

        // Detokenize
        let output = self.model.tokens_to_str(&output_tokens)
            .map_err(|e| LLMError::InferenceFailed(format!("Detokenization failed: {}", e)))?;

        debug!(output_len = output.len(), "Generation complete");

        // Parse for tool calls
        self.parse_output(&output, tool_schemas)
    }

    // ─── MOCK INFERENCE (no llama.cpp) ────────────────────────

    #[cfg(not(feature = "llama-cpp"))]
    async fn inference_mock(
        &self,
        _prompt: &str,
        tool_schemas: &[Value],
        _config: &AgentConfig,
    ) -> Result<LLMResponse, LLMError> {
        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        
        // Simulate tool call if tools available and no tool results yet
        if !tool_schemas.is_empty() {
            let tool_name = tool_schemas[0]["name"].as_str().unwrap_or("web_search");
            return Ok(LLMResponse::ToolCall {
                name: tool_name.to_string(),
                arguments: serde_json::json!({"query": "example"}),
            });
        }
        
        Ok(LLMResponse::Text(
            "[MOCK] This is a simulated response. Enable 'llama-cpp' feature for real inference.".to_string()
        ))
    }

    // ─── PROMPT BUILDER ───────────────────────────────────────

    fn build_prompt(&self, messages: &[ChatMessage], tool_schemas: &[Value]) -> String {
        let mut prompt = String::new();
        
        // System / tool instructions
        if !tool_schemas.is_empty() {
            prompt.push_str("You have access to the following tools:\\n\\n");
            for schema in tool_schemas {
                prompt.push_str(&format!("{:#}\\n\\n", schema));
            }
            prompt.push_str(
                "To use a tool, respond with a JSON object in this format:\\n"
            );
            prompt.push_str(
                '{"tool": "tool_name", "arguments": {"arg1": "value1"}}\\n\\n'
            );
            prompt.push_str("If no tool is needed, respond normally.\\n\\n");
        }

        // Messages
        for msg in messages {
            match msg.role.as_str() {
                "system" => prompt.push_str(&format!("<|system|>\\n{}\\n", msg.content)),
                "user" => prompt.push_str(&format!("<|user|>\\n{}\\n", msg.content)),
                "assistant" => prompt.push_str(&format!("<|assistant|>\\n{}\\n", msg.content)),
                "tool" => prompt.push_str(&format!("<|tool|>\\n{}\\n", msg.content)),
                _ => prompt.push_str(&format!("{}: {}\\n", msg.role, msg.content)),
            }
        }
        
        prompt.push_str("<|assistant|>\\n");
        prompt
    }

    // ─── OUTPUT PARSER ────────────────────────────────────────

    fn parse_output(&self, output: &str, tool_schemas: &[Value]) -> Result<LLMResponse, LLMError> {
        // Try to parse as tool call JSON
        if let Ok(json) = serde_json::from_str::<Value>(output.trim()) {
            if let Some(tool_name) = json.get("tool").and_then(|v| v.as_str()) {
                if let Some(args) = json.get("arguments") {
                    // Validate tool exists
                    let valid = tool_schemas.iter().any(|s| {
                        s.get("name").and_then(|n| n.as_str()) == Some(tool_name)
                    });
                    
                    if valid {
                        return Ok(LLMResponse::ToolCall {
                            name: tool_name.to_string(),
                            arguments: args.clone(),
                        });
                    }
                }
            }
        }
        
        // Plain text response
        Ok(LLMResponse::Text(output.trim().to_string()))
    }
}

// ═══════════════════════════════════════════════════════════════
// Model Manager — Download, cache, list models
// ═══════════════════════════════════════════════════════════════

use std::path::PathBuf;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub id: String,
    pub filename: String,
    pub path: PathBuf,
    pub size_bytes: u64,
    pub parameters: String,
    pub quantization: String,
    pub downloaded_at: Option<String>,
}

pub struct ModelManager {
    models_dir: PathBuf,
}

impl ModelManager {
    pub fn new() -> Result<Self, LLMError> {
        let models_dir = dirs::home_dir()
            .ok_or_else(|| LLMError::InferenceFailed("No home dir".to_string()))?
            .join(".meridian")
            .join("models");
        
        std::fs::create_dir_all(&models_dir)
            .map_err(|e| LLMError::InferenceFailed(e.to_string()))?;
        
        Ok(Self { models_dir })
    }

    pub fn list_local_models(&self) -> Result<Vec<ModelInfo>, LLMError> {
        let mut models = Vec::new();
        
        if let Ok(entries) = std::fs::read_dir(&self.models_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("gguf") {
                    let metadata = std::fs::metadata(&path).ok();
                    let size = metadata.as_ref().map(|m| m.len()).unwrap_or(0);
                    
                    let filename = path.file_name()
                        .and_then(|s| s.to_str())
                        .unwrap_or("unknown")
                        .to_string();
                    
                    models.push(ModelInfo {
                        id: filename.clone(),
                        filename: filename.clone(),
                        path,
                        size_bytes: size,
                        parameters: Self::guess_parameters(&filename),
                        quantization: Self::guess_quantization(&filename),
                        downloaded_at: metadata.and_then(|m| {
                            m.modified().ok()?.duration_since(std::time::UNIX_EPOCH).ok()
                                .map(|d| d.as_secs().to_string())
                        }),
                    });
                }
            }
        }
        
        Ok(models)
    }

    pub fn get_model_path(&self, model_id: &str) -> PathBuf {
        self.models_dir.join(model_id)
    }

    fn guess_parameters(filename: &str) -> String {
        if filename.contains("70b") { "70B".to_string() }
        else if filename.contains("34b") { "34B".to_string() }
        else if filename.contains("13b") { "13B".to_string() }
        else if filename.contains("8b") || filename.contains("7b") { "7-8B".to_string() }
        else if filename.contains("3b") { "3B".to_string() }
        else { "Unknown".to_string() }
    }

    fn guess_quantization(filename: &str) -> String {
        if filename.contains("Q4_K_M") { "Q4_K_M".to_string() }
        else if filename.contains("Q5_K_M") { "Q5_K_M".to_string() }
        else if filename.contains("Q8_0") { "Q8_0".to_string() }
        else if filename.contains("fp16") { "FP16".to_string() }
        else { "Unknown".to_string() }
    }
}
'''

with open('/mnt/agents/output/meridian-core/src/llm/bindings.rs', 'w') as f:
    f.write(llm_bindings_rs)
print("✅ src/llm/bindings.rs")
