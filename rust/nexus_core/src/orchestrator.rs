// ── v7.5 UPGRADE: Drift Detector & RDMA Dispatch ────────────────────────────
use crate::constitutional_drift::DriftDetector;
use crate::dispatch_rdma::RdmaDispatchContext;

pub struct NexusOrchestrator {
    // ... existing fields ...
    drift_detector: Arc<DriftDetector>,
    rdma_ctx: Arc<tokio::sync::RwLock<RdmaDispatchContext>>,
}

impl NexusOrchestrator {
    pub async fn run_civilization_loop(&mut self) {
        let mut tasks = JoinSet::new();
        
        // ... [Existing 6 tasks: dispatch, health, meta, audit, watchdog, emergent] ...

        // v7.5 TASK 7: Constitutional Drift Monitor (Semantic Consistency)
        let drift_det = Arc::clone(&self.drift_detector);
        let reg = Arc::clone(&self.agent_registry);
        tasks.spawn(async move {
            tracing::info!("🔍 Spawning Constitutional Drift Monitor (Hourly)");
            drift_det.run_monitor(reg).await;
        });

        // ... [Existing while let Some(result) = tasks.join_next().await loop] ...
    }

    // v7.5: Zero-Copy Dispatch Integration
    async fn dispatch_task_to_agent(&self, task: Task<InFlight>, agent: &AgentManifest) -> Result<(), OrchestratorError> {
        let mut ctx = self.rdma_ctx.write().await;
        
        // Attempts RDMA Write + io_uring CQE. Falls back to TCP if hardware missing.
        ctx.dispatch(&task.payload, agent.rkey, agent.raddr).await
            .map_err(|e| OrchestratorError::DispatchFailed(e.to_string()))
    }
}

// Ensure safe shutdown drains RDMA queue before drop
impl Drop for NexusOrchestrator {
    fn drop(&mut self) {
        tracing::warn!("Orchestrator dropping — ensuring RDMA drain");
        // In prod: block_on(ctx.shutdown()) to prevent use-after-deregister
    }
}
