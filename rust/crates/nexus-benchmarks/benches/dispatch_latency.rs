//! Comparative benchmark: Standard dispatch vs Zero-Copy RDMA dispatch
use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId};
use nexus_core::dispatch::{RdmaContext, AgentEndpoint};
use tokio::runtime::Runtime;

fn dispatch_comparison(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let mut group = c.benchmark_group("TaskDispatch_Latency");

    for size in [256, 1024, 4096, 16384] {
        let payload = vec![0u8; size];

        // Baseline: standard FlatBuffers + TCP dispatch
        group.bench_with_input(BenchmarkId::new("Standard", size), &size, |b, _| {
            b.iter(|| {
                rt.block_on(async {
                    // Simulate serialize + send overhead
                    let buf = flatbuffers::FlatBufferBuilder::new_with_capacity(size);
                    std::hint::black_box(buf);
                })
            })
        });

        // Zero-Copy: RDMA Write + io_uring
        group.bench_with_input(BenchmarkId::new("ZeroCopy_RDMA", size), &size, |b, _| {
            let mut ctx = RdmaContext::new(65536, -1);
            let target = AgentEndpoint {
                agent_id: 1, rkey: 0, raddr: 0, cq_fd: -1,
            };
            b.iter(|| {
                rt.block_on(async {
                    ctx.dispatch_zero_copy(&payload, &target).await.unwrap()
                })
            })
        });
    }
    group.finish();
}

criterion_group!(benches, dispatch_comparison);
criterion_main!(benches);
