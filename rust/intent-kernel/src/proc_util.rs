use std::io::{Read, Write};
use std::process::{Command, Output, Stdio};
use std::thread;
use std::time::{Duration, Instant};

/// Run a command with a hard wall-clock limit.
///
/// Returns `Err` when the process could not start or ran past `timeout`
/// (it is killed then). stdout/stderr are drained on their own threads so a
/// chatty child cannot deadlock on a full pipe.
pub fn run_with_timeout(
    mut cmd: Command,
    stdin: Option<Vec<u8>>,
    timeout: Duration,
) -> Result<Output, String> {
    cmd.stdin(if stdin.is_some() {
        Stdio::piped()
    } else {
        Stdio::null()
    })
    .stdout(Stdio::piped())
    .stderr(Stdio::piped());

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("could not start process: {e}"))?;

    let mut out_pipe = child.stdout.take();
    let mut err_pipe = child.stderr.take();
    let out_reader = thread::spawn(move || {
        let mut buf = Vec::new();
        if let Some(pipe) = out_pipe.as_mut() {
            let _ = pipe.read_to_end(&mut buf);
        }
        buf
    });
    let err_reader = thread::spawn(move || {
        let mut buf = Vec::new();
        if let Some(pipe) = err_pipe.as_mut() {
            let _ = pipe.read_to_end(&mut buf);
        }
        buf
    });
    if let (Some(data), Some(mut pipe)) = (stdin, child.stdin.take()) {
        // Written on its own thread; dropping the pipe afterwards closes stdin.
        thread::spawn(move || {
            let _ = pipe.write_all(&data);
        });
    }

    let deadline = Instant::now() + timeout;
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if Instant::now() >= deadline => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(format!("timed out after {}s", timeout.as_secs()));
            }
            Ok(None) => thread::sleep(Duration::from_millis(50)),
            Err(e) => {
                let _ = child.kill();
                return Err(format!("could not wait for process: {e}"));
            }
        }
    };

    Ok(Output {
        status,
        stdout: out_reader.join().unwrap_or_default(),
        stderr: err_reader.join().unwrap_or_default(),
    })
}

/// Seconds from an environment variable, or `default` when unset or invalid.
pub fn timeout_from_env(var: &str, default: u64) -> Duration {
    let secs = std::env::var(var)
        .ok()
        .and_then(|v| v.trim().parse::<u64>().ok())
        .filter(|s| *s > 0)
        .unwrap_or(default);
    Duration::from_secs(secs)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn python() -> Command {
        Command::new("python")
    }

    #[test]
    fn slow_process_is_killed_at_the_deadline() {
        let mut cmd = python();
        cmd.args(["-c", "import time; time.sleep(30)"]);
        let started = Instant::now();
        let res = run_with_timeout(cmd, None, Duration::from_secs(1));
        assert!(res.unwrap_err().contains("timed out"));
        assert!(started.elapsed() < Duration::from_secs(10));
    }

    #[test]
    fn stdin_reaches_the_child_and_output_comes_back() {
        let mut cmd = python();
        cmd.args(["-c", "import sys; print(sys.stdin.read().upper())"]);
        let out = run_with_timeout(cmd, Some(b"hello".to_vec()), Duration::from_secs(20)).unwrap();
        assert!(out.status.success());
        assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "HELLO");
    }

    #[test]
    fn missing_binary_is_an_error_not_a_success() {
        let cmd = Command::new("definitely-not-a-real-binary-ik");
        assert!(run_with_timeout(cmd, None, Duration::from_secs(5)).is_err());
    }
}
