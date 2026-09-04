use crate::memory::{MemoryKind, MemoryNode};
use crate::proof::ProofEvent;
use anyhow::{bail, Context};
use serde::Serialize;
use std::fmt;
use std::time::Duration;

pub const SUPABASE_URL_ENV: &str = "IK_SUPABASE_URL";
pub const SUPABASE_SECRET_KEY_ENV: &str = "IK_SUPABASE_SECRET_KEY";

const MEMORY_TABLE: &str = "ik_memory_nodes";
const PROOF_TABLE: &str = "ik_proof_events";
const SYNC_BATCH_SIZE: usize = 100;

pub struct SupabaseConfig {
    base_url: String,
    secret_key: String,
}

impl fmt::Debug for SupabaseConfig {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SupabaseConfig")
            .field("base_url", &self.base_url)
            .field("secret_key", &"[redacted]")
            .finish()
    }
}

impl SupabaseConfig {
    pub fn new(base_url: impl Into<String>, secret_key: impl Into<String>) -> anyhow::Result<Self> {
        let base_url = base_url.into().trim().trim_end_matches('/').to_string();
        let secret_key = secret_key.into().trim().to_string();

        if secret_key.is_empty() {
            bail!("{} must not be empty", SUPABASE_SECRET_KEY_ENV);
        }

        let is_remote_https = base_url.starts_with("https://") && base_url.len() > "https://".len();
        let is_local_http = ["http://localhost", "http://127.0.0.1"]
            .iter()
            .any(|prefix| base_url.starts_with(prefix));

        if !(is_remote_https || is_local_http)
            || base_url.contains('?')
            || base_url.contains('#')
        {
            bail!(
                "{} must be an HTTPS URL or a local Supabase URL",
                SUPABASE_URL_ENV
            );
        }

        Ok(Self {
            base_url,
            secret_key,
        })
    }

    pub fn from_env() -> anyhow::Result<Option<Self>> {
        match (
            std::env::var(SUPABASE_URL_ENV).ok(),
            std::env::var(SUPABASE_SECRET_KEY_ENV).ok(),
        ) {
            (None, None) => Ok(None),
            (Some(base_url), Some(secret_key)) => Self::new(base_url, secret_key).map(Some),
            _ => bail!(
                "Set both {} and {} before syncing",
                SUPABASE_URL_ENV,
                SUPABASE_SECRET_KEY_ENV
            ),
        }
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    fn secret_key(&self) -> &str {
        &self.secret_key
    }
}

pub struct SupabaseReplicator {
    config: SupabaseConfig,
    agent: ureq::Agent,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SyncReport {
    pub memory_nodes_synced: usize,
    pub proof_events_synced: usize,
}

impl SupabaseReplicator {
    pub fn new(config: SupabaseConfig) -> Self {
        let agent_config = ureq::Agent::config_builder()
            .timeout_global(Some(Duration::from_secs(15)))
            .build();
        let agent: ureq::Agent = agent_config.into();

        Self { config, agent }
    }

    pub fn sync(
        &self,
        memory_nodes: &[MemoryNode],
        proof_events: &[ProofEvent],
    ) -> anyhow::Result<SyncReport> {
        let memory_rows: Vec<_> = memory_nodes
            .iter()
            .map(|node| MemoryRow {
                id: &node.id,
                kind: memory_kind_name(&node.kind),
                content: &node.content,
                recorded_at: &node.timestamp,
            })
            .collect();

        let proof_rows: Vec<_> = proof_events
            .iter()
            .map(|event| ProofRow {
                proof_id: &event.proof_id,
                mission_id: &event.mission_id,
                event_type: &event.event,
                occurred_at: &event.timestamp,
                input: &event.input,
                output: &event.output,
                hash_version: event.hash_version,
                prev_hash: &event.prev_hash,
                hash: &event.hash,
            })
            .collect();

        let memory_nodes_synced = self.append_rows(MEMORY_TABLE, "id", &memory_rows)?;
        let proof_events_synced = self.append_rows(PROOF_TABLE, "proof_id", &proof_rows)?;

        Ok(SyncReport {
            memory_nodes_synced,
            proof_events_synced,
        })
    }

    fn append_rows<T: Serialize>(
        &self,
        table: &str,
        conflict_column: &str,
        rows: &[T],
    ) -> anyhow::Result<usize> {
        for batch in rows.chunks(SYNC_BATCH_SIZE) {
            let endpoint = self.endpoint(table, conflict_column);
            let authorization = format!("Bearer {}", self.config.secret_key());

            self.agent
                .post(&endpoint)
                .header("apikey", self.config.secret_key())
                .header("Authorization", &authorization)
                .header("Prefer", "resolution=ignore-duplicates,return=minimal")
                .send_json(batch)
                .with_context(|| format!("Supabase append failed for table '{}'", table))?;
        }

        Ok(rows.len())
    }

    fn endpoint(&self, table: &str, conflict_column: &str) -> String {
        format!(
            "{}/rest/v1/{}?on_conflict={}",
            self.config.base_url(),
            table,
            conflict_column
        )
    }
}

#[derive(Serialize)]
struct MemoryRow<'a> {
    id: &'a str,
    kind: &'a str,
    content: &'a str,
    recorded_at: &'a str,
}

#[derive(Serialize)]
struct ProofRow<'a> {
    proof_id: &'a str,
    mission_id: &'a str,
    event_type: &'a str,
    occurred_at: &'a str,
    input: &'a serde_json::Value,
    output: &'a serde_json::Value,
    hash_version: u8,
    prev_hash: &'a str,
    hash: &'a str,
}

fn memory_kind_name(kind: &MemoryKind) -> &'static str {
    match kind {
        MemoryKind::Mission => "mission",
        MemoryKind::Playbook => "playbook",
        MemoryKind::Lesson => "lesson",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_requires_https_for_remote_projects() {
        assert!(SupabaseConfig::new("http://example.com", "secret").is_err());
        assert!(SupabaseConfig::new("https://example.supabase.co", "secret").is_ok());
        assert!(SupabaseConfig::new("http://127.0.0.1:54321", "secret").is_ok());
    }

    #[test]
    fn config_debug_output_redacts_the_secret() {
        let config = SupabaseConfig::new("https://example.supabase.co", "very-secret-key").unwrap();
        let debug = format!("{:?}", config);

        assert!(!debug.contains("very-secret-key"));
        assert!(debug.contains("[redacted]"));
    }

    #[test]
    fn endpoint_uses_the_primary_key_as_conflict_target() {
        let config = SupabaseConfig::new("https://example.supabase.co/", "secret").unwrap();
        let replicator = SupabaseReplicator::new(config);

        assert_eq!(
            replicator.endpoint(MEMORY_TABLE, "id"),
            "https://example.supabase.co/rest/v1/ik_memory_nodes?on_conflict=id"
        );
    }
}
