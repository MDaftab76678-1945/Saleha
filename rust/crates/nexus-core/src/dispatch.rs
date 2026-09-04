//! crates/nexus-core/src/dispatch.rs
//! Zero-Copy Task Dispatch Engine
//!
//! Eliminates serialization copy overhead by writing directly into
//! pre-registered remote memory regions via RDMA, then notifying
//! the receiver via io_uring CQE (kernel bypass).
//!
//! Performance Target: <10μs dispatch latency (vs ~40μs with TCP+FlatBuffers)

use std::os::fd::RawFd;
use std::sync::Arc;
use tokio::io::Interest;
use thiserror::Error;

/// Pre-registered RDMA memory region for zero-copy transfers.
/// In production: backed by ibv_reg_mr() with IBV_ACCESS_REMOTE_WRITE.
pub struct RdmaContext {
    /// Local send buffer registered with NIC
    send_buffer: Vec<u8>,
    /// Remote key for target agent's receive buffer
    rkey: u32,
    /// io_uring completion queue file descriptor
    cq_fd: RawFd,
    /// Maximum payload size for this context
    max_payload: usize,
}

/// Remote agent endpoint metadata
#[derive(Debug, Clone)]
pub struct AgentEndpoint {
    pub agent_id: u64,
    pub rkey: u32,
    pub raddr: u64,
    pub cq_fd: RawFd,
}

impl RdmaContext {
    pub fn new(max_payload: usize, cq_fd: RawFd) -> Self {
        Self {
            send_buffer: vec![0u8; max_payload],
            rkey: 0,
            cq_fd,
            max_payload,
        }
    }

    /// Dispatch task payload to remote agent with zero-copy semantics.
    ///
    /// Flow:
    ///   1. Copy payload into pre-registered local buffer (single memcpy, no alloc)
    ///   2. Post one-sided RDMA_WRITE to agent's receive buffer (kernel bypass)
    ///   3. Submit io_uring CQE notification (no syscall overhead)
    pub async fn dispatch_zero_copy(
        &mut self,
        payload: &[u8],
        target: &AgentEndpoint,
    ) -> Result<(), DispatchError> {
        // Guard: payload must fit in pre-registered buffer
        if payload.len() > self.max_payload {
            return Err(DispatchError::PayloadTooLarge {
                max: self.max_payload,
                got: payload.len(),
            });
        }

        // Step 1: Single copy into registered buffer (no heap allocation)
        self.send_buffer[..payload.len()].copy_from_slice(payload);

        // Step 2: One-sided RDMA Write to remote agent
        // In production: ibv_post_send(wr.opcode = IBV_WR_RDMA_WRITE)
        self.rdma_write(target.rkey, target.raddr, &self.send_buffer[..payload.len()])
            .await
            .map_err(|_| DispatchError::RdmaWriteFailed)?;

        // Step 3: Notify agent via io_uring CQE (kernel-bypass)
        // Avoids write()/epoll() syscall overhead entirely
        self.notify_completion(target.cq_fd)
            .await
            .map_err(|_| DispatchError::NotificationFailed)?;

        Ok(())
    }

    /// One-sided RDMA Write — kernel bypass data transfer
    async fn rdma_write(&self, rkey: u32, raddr: u64, data: &[u8]) -> Result<(), ()> {
        // Production implementation:
        //   let mut wr = ibv_send_wr::default();
        //   wr.opcode = ibv_wr_opcode::IBV_WR_RDMA_WRITE;
        //   wr.wr.rdma.remote_addr = raddr;
        //   wr.wr.rdma.rkey = rkey;
        //   ibv_post_send(qp, &mut wr, &mut bad_wr);
        //
        // Stub for compilation:
        let _ = (rkey, raddr, data);
        Ok(())
    }

    /// io_uring CQE notification — kernel bypass signaling
    async fn notify_completion(&self, cq_fd: RawFd) -> Result<(), ()> {
        // Production implementation:
        //   let entry = io_uring_sqe::new(IORING_OP_NOP);
        //   entry.set_user_data(agent_id);
        //   ring.submit_and_wait(1)?;
        //
        // Stub for compilation:
        let _ = cq_fd;
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum DispatchError {
    #[error("Payload too large: max {max} bytes, got {got}")]
    PayloadTooLarge { max: usize, got: usize },

    #[error("RDMA write failed — check NIC status and remote rkey validity")]
    RdmaWriteFailed,

    #[error("io_uring notification failed — check CQ fd and ring state")]
    NotificationFailed,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_payload_too_large_rejected() {
        let mut ctx = RdmaContext::new(1024, -1);
        let target = AgentEndpoint {
            agent_id: 1,
            rkey: 0x1234,
            raddr: 0xDEAD_BEEF,
            cq_fd: -1,
        };
        let oversized = vec![0u8; 2048];
        let result = ctx.dispatch_zero_copy(&oversized, &target).await;
        assert!(matches!(result, Err(DispatchError::PayloadTooLarge { .. })));
    }

    #[tokio::test]
    async fn test_valid_payload_accepted() {
        let mut ctx = RdmaContext::new(4096, -1);
        let target = AgentEndpoint {
            agent_id: 1,
            rkey: 0x1234,
            raddr: 0xDEAD_BEEF,
            cq_fd: -1,
        };
        let payload = vec![42u8; 256];
        // Stub always succeeds — real test requires RDMA hardware
        let result = ctx.dispatch_zero_copy(&payload, &target).await;
        assert!(result.is_ok());
    }
}
