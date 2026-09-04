// crates/meridian-bridge/src/lib.rs
use reqwest::Client;
use serde_json::json;

/// Bridges MUKTI cloud agents with MERIDIAN local execution
pub struct MuktiBridge {
    mukti_endpoint: String,
    api_key: String,
    meridian_core: meridian_core::MeridianCore,
    client: Client,
}

impl MuktiBridge {
    pub async fn run(&self) -> Result<(), BridgeError> {
        // 1. Register this MERIDIAN instance with MUKTI
        self.register_with_mukti().await?;

        // 2. Poll MUKTI for tasks
        loop {
            let task = self.poll_task().await?;
            if let Some(task) = task {
                // 3. Execute locally via meridian-core
                let result = self.meridian_core
                    .execute_agent(&task.agent_name, &task.input)
                    .await?;

                // 4. Send results back to MUKTI
                self.submit_result(task.id, result).await?;
            }
            tokio::time::sleep(Duration::from_secs(5)).await;
        }
    }

    pub async fn handle_mukti_request(
        &self,
        req: MuktiRequest
    ) -> Result<MuktiResponse, BridgeError> {
        match req.action {
            Action::RunAgent { name, input } => {
                let output = self.meridian_core.run_agent(&name, &input).await?;
                Ok(MuktiResponse { output, status: "success" })
            }
            Action::GetStatus => {
                let status = self.meridian_core.system_status().await?;
                Ok(MuktiResponse { output: json!(status), status: "success" })
            }
            Action::ListModels => {
                let models = self.meridian_core.list_local_models().await?;
                Ok(MuktiResponse { output: json!(models), status: "success" })
            }
        }
    }
}