use std::process::Command;

pub struct VerifyResult {
    pub success: bool,
    pub compiled: bool,
    pub output: String,
    pub compile_errors: String,
    pub attempts: usize,
}

pub struct Verifier {
    max_retries: usize,
}

impl Verifier {
    pub fn new() -> Self {
        Self { max_retries: 3 }
    }

    pub fn max_retries(&self) -> usize {
        self.max_retries
    }

    pub fn verify_rust_code(&self, file_path: &str) -> VerifyResult {
        let exe_name = "verify_output.exe";

        // Windows requires .\ prefix to run exe in current directory
        let exe_run_path = if cfg!(windows) {
            format!(".\\{}", exe_name)
        } else {
            format!("./{}", exe_name)
        };

        println!("[VERIFY] Compiling {}...", file_path);
        let compile = Command::new("rustc")
            .args(&[file_path, "-o", exe_name])
            .output();

        match compile {
            Ok(output) if output.status.success() => {
                println!("[VERIFY] ✓ Compilation successful");
                println!("[VERIFY] Running compiled code...");

                let run = Command::new(&exe_run_path).output();
                let _ = std::fs::remove_file(exe_name);

                match run {
                    Ok(run_output) if run_output.status.success() => {
                        let stdout = String::from_utf8_lossy(&run_output.stdout).to_string();
                        println!("[VERIFY] ✓ Execution successful");
                        println!("[VERIFY] Output:\n{}", stdout);
                        VerifyResult {
                            success: true,
                            compiled: true,
                            output: stdout,
                            compile_errors: String::new(),
                            attempts: 1,
                        }
                    }
                    Ok(run_output) => {
                        let stderr = String::from_utf8_lossy(&run_output.stderr).to_string();
                        println!("[VERIFY] ✗ Runtime error");
                        VerifyResult {
                            success: false,
                            compiled: true,
                            output: String::new(),
                            compile_errors: format!("Runtime error: {}", stderr),
                            attempts: 1,
                        }
                    }
                    Err(e) => VerifyResult {
                        success: false,
                        compiled: true,
                        output: String::new(),
                        compile_errors: format!("Failed to run: {}", e),
                        attempts: 1,
                    },
                }
            }
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr).to_string();
                println!("[VERIFY] ✗ Compilation failed");
                VerifyResult {
                    success: false,
                    compiled: false,
                    output: String::new(),
                    compile_errors: stderr,
                    attempts: 1,
                }
            }
            Err(e) => VerifyResult {
                success: false,
                compiled: false,
                output: String::new(),
                compile_errors: format!("rustc not found: {}", e),
                attempts: 1,
            },
        }
    }

    pub fn verify_python_code(&self, file_path: &str) -> VerifyResult {
        println!("[VERIFY] Running Python syntax check...");
        let check = Command::new("python")
            .args(&["-m", "py_compile", file_path])
            .output();

        match check {
            Ok(output) if output.status.success() => {
                println!("[VERIFY] ✓ Python syntax valid");

                let run = Command::new("python").args(&[file_path]).output();

                match run {
                    Ok(run_output) => {
                        let stdout = String::from_utf8_lossy(&run_output.stdout).to_string();
                        VerifyResult {
                            success: run_output.status.success(),
                            compiled: true,
                            output: stdout,
                            compile_errors: String::new(),
                            attempts: 1,
                        }
                    }
                    Err(e) => VerifyResult {
                        success: false,
                        compiled: true,
                        output: String::new(),
                        compile_errors: format!("Run failed: {}", e),
                        attempts: 1,
                    },
                }
            }
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr).to_string();
                VerifyResult {
                    success: false,
                    compiled: false,
                    output: String::new(),
                    compile_errors: stderr,
                    attempts: 1,
                }
            }
            Err(e) => VerifyResult {
                success: false,
                compiled: false,
                output: String::new(),
                compile_errors: format!("python not found: {}", e),
                attempts: 1,
            },
        }
    }
}
