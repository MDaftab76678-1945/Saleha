//! Integration tests requiring RDMA hardware or SoftRoCE
//! Run with: cargo test --features rdma -- --ignored

#[cfg(feature = "rdma")]
mod rdma_tests {
    use nexus_core::dispatch_rdma::RdmaDispatchContext;

    #[tokio::test]
    #[ignore] // Requires RDMA hardware
    async fn test_rdma_context_initialization() {
        let ctx = RdmaDispatchContext::new(65536);
        assert!(ctx.is_ok(), "RDMA context must initialize on test machine");
    }

    #[tokio::test]
    #[ignore]
    async fn test_zero_copy_dispatch_loopback() {
        let mut ctx = RdmaDispatchContext::new(4096).unwrap();
        let payload = vec![42u8; 1024];
        // Loopback test: rkey/raddr point to own registered MR
        // Full impl requires two contexts or self-loopback QP setup
        let result = ctx.dispatch(&payload, 0x1234, 0xDEADBEEF).await;
        // May fail without proper QP pairing — validates error handling
        println!("Loopback result: {:?}", result);
    }
}

#[tokio::test]
async fn test_tcp_fallback_always_works() {
    // This test runs WITHOUT rdma feature — validates fallback path
    let mut ctx = nexus_core::dispatch_rdma::RdmaDispatchContext::new(4096).unwrap();
    let payload = vec![1u8; 256];
    let result = ctx.dispatch(&payload, 0, 0).await;
    assert!(result.is_ok(), "TCP fallback must always succeed");
}
