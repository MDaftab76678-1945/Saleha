use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId};
use nexus_core::dispatch_rdma::RdmaDispatchContext;
use tokio::runtime::Runtime;

fn benchmark_dispatch_latency(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let mut group = c.benchmark_group("Dispatch_Latency_v75");

    for size in [256, 1024, 4096, 16384] {
        let payload = vec![42u8; size];
        
        // v7 Baseline: TCP + FlatBuffers Serialize
        group.bench_with_input(BenchmarkId::new("TCP_v7", size), &size, |b, _| {
            b.iter(|| rt.block_on(async { tcp_dispatch_stub(&payload).await }))
        });

        // v7.5 Upgrade: Zero-Copy RDMA + io_uring
        group.bench_with_input(BenchmarkId::new("RDMA_ZeroCopy_v75", size), &size, |b, _| {
            let mut ctx = RdmaDispatchContext::new(65536);
            b.iter(|| rt.block_on(async { ctx.dispatch(&payload, 0x1234, 0xDEADBEEF).await.unwrap() }))
        });
    }
    group.finish();
}
// ... stub for tcp_dispatch_stub ...
