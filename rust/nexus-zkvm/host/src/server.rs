// nexus-zkvm/host/src/server.rs
use tonic::{transport::Server, Request, Response, Status};
use risc0_zkvm::{default_prover, ExecutorEnv, Receipt};

// Import generated protobuf code
pub mod nexus_proto {
    tonic::include_proto!("nexus.v8");
}

use nexus_proto::{
    mie_prover_service_server::{MieProverService, MieProverServiceServer},
    MieProofRequest, MieProofResponse, MieProofReceipt, MieJournal, VerifyResponse,
};

pub struct MIEProverServer {
    elf: Vec<u8>,
}

#[tonic::async_trait]
impl MieProverService for MIEProverServer {
    async fn generate_mie_proof(
        &self,
        request: Request<MieProofRequest>,
    ) -> Result<Response<MieProofResponse>, Status> {
        let req = request.into_inner();
        
        // 1. Setup zkVM Environment
        let env = ExecutorEnv::builder()
            .write(&req) // Pass the entire protobuf message as input
            .map_err(|e| Status::internal(format!("Env build failed: {}", e)))?
            .build()
            .map_err(|e| Status::internal(format!("Env build failed: {}", e)))?;

        // 2. Execute Prover (This is the compute-heavy step)
        let prover = default_prover();
        let receipt = prover
            .prove(env, &self.elf)
            .map_err(|e| Status::internal(format!("Proving failed: {}", e)))?;

        // 3. Extract Journal to get execution metrics
        let journal: MieJournal = receipt
            .journal
            .decode()
            .map_err(|e| Status::internal(format!("Journal decode failed: {}", e)))?;

        // 4. Construct Response
        let response = MieProofResponse {
            success: true,
            error_message: String::new(),
            receipt: Some(MieProofReceipt {
                journal_data: receipt.journal.bytes.clone(),
                proof_bytes: receipt.seal.clone(),
                execution_cycles: receipt.get_metadata().unwrap().cycles as u64,
            }),
        };

        Ok(Response::new(response))
    }

    async fn verify_mie_proof(
        &self,
        request: Request<MieProofReceipt>,
    ) -> Result<Response<VerifyResponse>, Status> {
        let req = request.into_inner();
        let receipt = Receipt::new(
            risc0_zkvm::ReceiptMetadata::default(), // Simplified for demo
            req.proof_bytes,
        );

        // Fast verification (O(1) relative to execution)
        let is_valid = receipt.verify(&self.elf).is_ok();
        
        let journal = if is_valid {
            receipt.journal.decode().ok()
        } else {
            None
        };

        Ok(Response::new(VerifyResponse {
            is_valid,
            decoded_journal: journal,
            error_message: if !is_valid { "Invalid cryptographic proof".to_string() } else { String::new() },
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "0.0.0.0:50051".parse()?;
    let elf = include_bytes!("../../guest/target/riscv32im-risc0-zkvm-elf/release/guest");
    
    let server = MIEProverServer { elf: elf.to_vec() };

    println!("NEXUS v8 MIE Prover gRPC Server listening on {}", addr);

    Server::builder()
        .add_service(MieProverServiceServer::new(server))
        .serve(addr)
        .await?;

    Ok(())
}
