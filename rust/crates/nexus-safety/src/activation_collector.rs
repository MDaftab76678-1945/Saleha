//! crates/nexus-safety/src/activation_collector.rs
//!
//! Non-blocking activation collector for MemoryArchivist.
//! Samples activations asynchronously via bounded channel — zero latency impact
//! on the retrieval hot path. Collected data feeds SAE training pipeline.

use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::debug;

const CHANNEL_CAPACITY: usize = 10_000; // ~40MB buffer at 4096-dim f32
const SAMPLE_RATE: f64 = 0.10;          // Sample 10% of retrievals for training

#[derive(Debug, Clone)]
pub struct ActivationSample {
    pub query_embedding: Vec<f32>,      // [768]
    pub archivist_activations: Vec<f32>, // [4096]
    pub retrieved_memory_ids: Vec<u64>,
    pub relevance_scores: Vec<f32>,
    pub timestamp_ns: u64,
    /// Human label (populated during annotation phase)
    pub label: Option<DeceptionLabel>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum DeceptionLabel {
    Clean,
    SelectiveOmission,
    EmotionalPriming,
    ContextDistortion,
    AuthorityMisattribution,
    TemporalReframing,
    Uncertain, // Annotator couldn't determine
}

pub struct ActivationCollector {
    tx: mpsc::Sender<ActivationSample>,
    sample_rate: f64,
    counter: Arc<std::sync::atomic::AtomicU64>,
}

impl ActivationCollector {
    pub fn new() -> (Self, mpsc::Receiver<ActivationSample>) {
        let (tx, rx) = mpsc::channel(CHANNEL_CAPACITY);
        (
            Self {
                tx,
                sample_rate: SAMPLE_RATE,
                counter: Arc::new(std::sync::atomic::AtomicU64::new(0)),
            },
            rx,
        )
    }

    /// Called inline during MemoryArchivist::retrieve().
    /// Non-blocking: drops sample if channel full (backpressure-safe).
    pub fn record(&self, sample: ActivationSample) {
        let count = self.counter.fetch_add(1, std::sync::atomic::Ordering::Relaxed);

        // Deterministic sampling (no RNG overhead on hot path)
        if (count % (1.0 / self.sample_rate) as u64) != 0 {
            return;
        }

        // try_send is non-blocking — never stalls retrieval
        match self.tx.try_send(sample) {
            Ok(()) => debug!("Activation sample recorded (total: {})", count),
            Err(mpsc::error::TrySendError::Full(_)) => {
                debug!("Activation channel full — dropping sample (backpressure)");
            }
            Err(_) => {} // Channel closed — shutdown in progress
        }
    }
}

/// Background task: drains channel and writes to disk for training
pub async fn activation_writer(mut rx: mpsc::Receiver<ActivationSample>, output_dir: &str) {
    let mut buffer: Vec<ActivationSample> = Vec::with_capacity(1000);
    let flush_interval = tokio::time::Duration::from_secs(60);
    let mut interval = tokio::time::interval(flush_interval);

    loop {
        tokio::select! {
            Some(sample) = rx.recv() => {
                buffer.push(sample);
                if buffer.len() >= 1000 {
                    flush_to_disk(&buffer, output_dir).await;
                    buffer.clear();
                }
            }
            _ = interval.tick() => {
                if !buffer.is_empty() {
                    flush_to_disk(&buffer, output_dir).await;
                    buffer.clear();
                }
            }
            else => break, // Channel closed
        }
    }
}

async fn flush_to_disk(samples: &[ActivationSample], output_dir: &str) {
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let path = format!("{}/activations_{}.jsonl", output_dir, timestamp);

    let mut lines = String::new();
    for s in samples {
        if let Ok(json) = serde_json::to_string(s) {
            lines.push_str(&json);
            lines.push('\n');
        }
    }

    if let Err(e) = tokio::fs::write(&path, &lines).await {
        tracing::error!("Failed to flush activations to {}: {}", path, e);
    } else {
        tracing::info!("Flushed {} activation samples to {}", samples.len(), path);
    }
}
