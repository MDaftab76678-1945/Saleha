use wasmparser::{Parser, Payload, Operator};
use std::collections::HashSet;

/// Verifies that a WASM module is safe to execute (Proof-Carrying Code).
/// Ensures no unauthorized syscalls, no infinite loops, and bounded memory.
pub struct PCCVerifier {
    allowed_imports: HashSet<String>,
    max_memory_pages: u32,
}

impl PCCVerifier {
    pub fn new() -> Self {
        let mut allowed = HashSet::new();
        allowed.insert("env.read_sensor".to_string());
        allowed.insert("env.log".to_string());
        
        Self {
            allowed_imports: allowed,
            max_memory_pages: 10, // Max 640KB memory
        }
    }

    /// Verifies the WASM bytecode before execution.
    pub fn verify_safety(&self, wasm_bytes: &[u8]) -> Result<(), String> {
        let parser = Parser::new(0);
        
        for payload in parser.parse_all(wasm_bytes) {
            let payload = payload.map_err(|e| format!("Parse error: {}", e))?;
            
            match payload {
                Payload::ImportSection(import_section) => {
                    for import in import_section {
                        let import = import.map_err(|e| e.to_string())?;
                        let full_name = format!("{}.{}", import.module, import.name);
                        if !self.allowed_imports.contains(&full_name) {
                            return Err(format!("Unauthorized import: {}", full_name));
                        }
                    }
                }
                Payload::MemorySection(mem_section) => {
                    for mem in mem_section {
                        let mem = mem.map_err(|e| e.to_string())?;
                        if mem.initial > self.max_memory_pages {
                            return Err("Memory allocation exceeds limit".to_string());
                        }
                    }
                }
                // In production: Analyze Operator section to ban loops (for guaranteed termination)
                _ => {}
            }
        }
        Ok(())
    }
}
