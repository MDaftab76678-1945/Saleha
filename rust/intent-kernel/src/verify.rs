use crate::proc_util::{run_with_timeout, timeout_from_env};
use std::process::Command;
use std::time::Duration;

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

impl Default for Verifier {
    fn default() -> Self {
        Self::new()
    }
}

/// True when the source contains at least one assertion for `language`.
///
/// Exit code 0 from a program with no assertions proves only that it did not
/// crash; it checks nothing about the task, so it must not count as verified.
pub fn has_assertions(code: &str, language: &str) -> bool {
    let markers: &[&str] = match language {
        "rust" => &["assert!(", "assert_eq!(", "assert_ne!("],
        "python" => &["assert ", "assert(", "self.assert"],
        "javascript" => &["console.assert(", "assert(", "assert."],
        _ => &[],
    };
    code.lines()
        .map(str::trim_start)
        .filter(|l| !l.starts_with("//") && !l.starts_with('#'))
        .any(|l| markers.iter().any(|m| l.contains(m)))
}

/// How long generated code may run before it is killed (IK_RUN_TIMEOUT_SECS).
pub fn run_timeout() -> Duration {
    timeout_from_env("IK_RUN_TIMEOUT_SECS", 30)
}

fn fail(compiled: bool, errors: String) -> VerifyResult {
    VerifyResult {
        success: false,
        compiled,
        output: String::new(),
        compile_errors: errors,
        attempts: 1,
    }
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
        let mut compile_cmd = Command::new("rustc");
        compile_cmd.args([file_path, "-o", exe_name]);
        let compile = run_with_timeout(compile_cmd, None, Duration::from_secs(120));

        match compile {
            Ok(output) if output.status.success() => {
                println!("[VERIFY] ✓ Compilation successful");
                println!("[VERIFY] Running compiled code...");

                let run = run_with_timeout(Command::new(&exe_run_path), None, run_timeout());
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
                        fail(true, format!("Runtime error: {}", stderr))
                    }
                    Err(e) => fail(true, format!("Failed to run: {}", e)),
                }
            }
            Ok(output) => {
                println!("[VERIFY] ✗ Compilation failed");
                fail(false, String::from_utf8_lossy(&output.stderr).to_string())
            }
            Err(e) => fail(false, format!("rustc did not run: {}", e)),
        }
    }

    pub fn verify_python_code(&self, file_path: &str) -> VerifyResult {
        println!("[VERIFY] Running Python syntax check...");
        let mut check_cmd = Command::new("python");
        check_cmd.args(["-m", "py_compile", file_path]);
        let check = run_with_timeout(check_cmd, None, Duration::from_secs(60));

        match check {
            Ok(output) if output.status.success() => {
                println!("[VERIFY] ✓ Python syntax valid");

                let mut run_cmd = Command::new("python");
                run_cmd.arg(file_path);
                match run_with_timeout(run_cmd, None, run_timeout()) {
                    Ok(run_output) if run_output.status.success() => VerifyResult {
                        success: true,
                        compiled: true,
                        output: String::from_utf8_lossy(&run_output.stdout).to_string(),
                        compile_errors: String::new(),
                        attempts: 1,
                    },
                    // A runtime failure must carry its traceback, or the fix
                    // prompt asks the model to repair an empty error.
                    Ok(run_output) => fail(
                        true,
                        format!(
                            "Runtime error: {}",
                            String::from_utf8_lossy(&run_output.stderr)
                        ),
                    ),
                    Err(e) => fail(true, format!("Run failed: {}", e)),
                }
            }
            Ok(output) => fail(false, String::from_utf8_lossy(&output.stderr).to_string()),
            Err(e) => fail(false, format!("python did not run: {}", e)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn assertion_detection_ignores_comments() {
        assert!(has_assertions("def f():\n    return 1\nassert f() == 1\n", "python"));
        assert!(!has_assertions("# assert nothing\nprint('hi')\n", "python"));
        assert!(has_assertions("fn main() { assert_eq!(1, 1); }", "rust"));
        assert!(!has_assertions("// assert_eq!(1, 1)\nfn main() {}", "rust"));
        assert!(!has_assertions("assert x", "cobol"));
    }
}
