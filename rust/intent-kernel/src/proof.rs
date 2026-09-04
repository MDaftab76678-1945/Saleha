use anyhow::{bail, Context};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

pub const LEGACY_PROOF_HASH_VERSION: u8 = 1;
pub const CURRENT_PROOF_HASH_VERSION: u8 = 2;

fn default_hash_version() -> u8 {
    LEGACY_PROOF_HASH_VERSION
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofEvent {
    pub proof_id: String,
    pub mission_id: String,
    pub event: String,
    pub timestamp: String,
    pub input: Value,
    pub output: Value,
    #[serde(default = "default_hash_version")]
    pub hash_version: u8,
    pub prev_hash: String,
    pub hash: String,
}

pub struct ProofLedger {
    path: PathBuf,
    last_hash: String,
}

impl ProofLedger {
    pub fn new(path: &str) -> anyhow::Result<Self> {
        let path = PathBuf::from(path);
        if let Some(parent) = path.parent().filter(|parent| !parent.as_os_str().is_empty()) {
            fs::create_dir_all(parent)?;
        }

        let events = Self::read_events(&path)?;
        if !Self::verify_events(&events)? {
            bail!("Existing proof ledger integrity check failed; refusing to append");
        }

        let last_hash = events
            .last()
            .map(|event| event.hash.clone())
            .unwrap_or_else(|| "genesis".to_string());

        Ok(Self { path, last_hash })
    }

    pub fn append(
        &mut self,
        mission_id: &str,
        event: &str,
        input: Value,
        output: Value,
    ) -> anyhow::Result<()> {
        let timestamp = chrono::Utc::now().to_rfc3339();
        let proof_id = format!(
            "proof_{}",
            chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
        );

        let mut proof = ProofEvent {
            proof_id,
            mission_id: mission_id.to_string(),
            event: event.to_string(),
            timestamp,
            input,
            output,
            hash_version: CURRENT_PROOF_HASH_VERSION,
            prev_hash: self.last_hash.clone(),
            hash: String::new(),
        };
        proof.hash = Self::hash_for_event(&proof)?;

        let mut file = fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(&self.path)?;

        use std::io::Write;
        let line = serde_json::to_string(&proof)? + "\n";
        file.write_all(line.as_bytes())?;

        self.last_hash = proof.hash;
        Ok(())
    }

    pub fn read_events(path: impl AsRef<Path>) -> anyhow::Result<Vec<ProofEvent>> {
        let path = path.as_ref();
        if !path.exists() {
            return Ok(Vec::new());
        }

        let content = fs::read_to_string(path)?;
        let mut events = Vec::new();

        for (line_number, line) in content.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }

            let event = serde_json::from_str(line)
                .with_context(|| format!("Invalid proof event at line {}", line_number + 1))?;
            events.push(event);
        }

        Ok(events)
    }

    pub fn verify_chain(&self) -> anyhow::Result<bool> {
        Self::verify_events(&Self::read_events(&self.path)?)
    }

    pub fn verify_events(events: &[ProofEvent]) -> anyhow::Result<bool> {
        let mut prev_hash = "genesis".to_string();

        for event in events {
            if event.prev_hash != prev_hash {
                return Ok(false);
            }

            if Self::hash_for_event(event)? != event.hash {
                return Ok(false);
            }

            prev_hash = event.hash.clone();
        }

        Ok(true)
    }

    fn hash_for_event(event: &ProofEvent) -> anyhow::Result<String> {
        match event.hash_version {
            LEGACY_PROOF_HASH_VERSION => {
                let payload = format!(
                    "{}:{}:{}:{}",
                    event.prev_hash, event.timestamp, event.event, event.input
                );
                Ok(Self::sha256(payload.as_bytes()))
            }
            CURRENT_PROOF_HASH_VERSION => {
                #[derive(Serialize)]
                struct ProofHashPayload<'a> {
                    version: u8,
                    proof_id: &'a str,
                    mission_id: &'a str,
                    event: &'a str,
                    timestamp: &'a str,
                    input: &'a Value,
                    output: &'a Value,
                    prev_hash: &'a str,
                }

                let payload = ProofHashPayload {
                    version: event.hash_version,
                    proof_id: &event.proof_id,
                    mission_id: &event.mission_id,
                    event: &event.event,
                    timestamp: &event.timestamp,
                    input: &event.input,
                    output: &event.output,
                    prev_hash: &event.prev_hash,
                };
                Ok(Self::sha256(&serde_json::to_vec(&payload)?))
            }
            unsupported => bail!("Unsupported proof hash version: {}", unsupported),
        }
    }

    fn sha256(data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        hasher
            .finalize()
            .iter()
            .map(|byte| format!("{:02x}", byte))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn v2_event() -> ProofEvent {
        let mut event = ProofEvent {
            proof_id: "proof_test".to_string(),
            mission_id: "mission_test".to_string(),
            event: "node.completed".to_string(),
            timestamp: "2026-08-11T00:00:00Z".to_string(),
            input: json!({"path": "example.txt"}),
            output: json!({"bytes_written": 5}),
            hash_version: CURRENT_PROOF_HASH_VERSION,
            prev_hash: "genesis".to_string(),
            hash: String::new(),
        };
        event.hash = ProofLedger::hash_for_event(&event).unwrap();
        event
    }

    #[test]
    fn v2_hash_covers_execution_output() {
        let event = v2_event();
        assert!(ProofLedger::verify_events(&[event.clone()]).unwrap());

        let mut tampered = event;
        tampered.output = json!({"bytes_written": 999});
        assert!(!ProofLedger::verify_events(&[tampered]).unwrap());
    }

    #[test]
    fn legacy_v1_events_remain_verifiable() {
        let mut event = ProofEvent {
            proof_id: "legacy_proof".to_string(),
            mission_id: "legacy_mission".to_string(),
            event: "plan.started".to_string(),
            timestamp: "2026-08-10T00:00:00Z".to_string(),
            input: json!({"plan_id": "legacy_plan"}),
            output: json!({"dry_run": false}),
            hash_version: LEGACY_PROOF_HASH_VERSION,
            prev_hash: "genesis".to_string(),
            hash: String::new(),
        };
        event.hash = ProofLedger::hash_for_event(&event).unwrap();

        assert!(ProofLedger::verify_events(&[event]).unwrap());
    }

    #[test]
    fn ledger_refuses_to_append_to_a_tampered_file() {
        let directory = std::env::temp_dir().join(format!(
            "ik-proof-test-{}-{}",
            std::process::id(),
            chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        let path = directory.join("proof.jsonl");

        let mut ledger = ProofLedger::new(path.to_str().unwrap()).unwrap();
        ledger
            .append(
                "mission_test",
                "node.completed",
                json!({"path": "example.txt"}),
                json!({"bytes_written": 5}),
            )
            .unwrap();
        drop(ledger);

        let mut events = ProofLedger::read_events(&path).unwrap();
        events[0].output = json!({"bytes_written": 999});
        fs::write(&path, format!("{}\n", serde_json::to_string(&events[0]).unwrap())).unwrap();

        assert!(ProofLedger::new(path.to_str().unwrap()).is_err());
        fs::remove_dir_all(directory).unwrap();
    }
}
