use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId, Throughput};
use nexus_consensus::{PbftNode, HotStuffNode};
use tokio::runtime::Runtime;

fn benchmark_consensus_scaling(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let mut group = c.benchmark_group("Consensus_Scaling_v7_vs_v75");
    group.sample_size(50);
    group.measurement_time(std::time::Duration::from_secs(15));

    for n in [10, 50, 100, 200, 500] {
        group.throughput(Throughput::Elements(n as u64));
        
        // v7 Baseline: PBFT (O(n²) message complexity)
        group.bench_with_input(BenchmarkId::new("PBFT_v7", n), &n, |b, &n| {
            b.iter(|| rt.block_on(async { PbftNode::simulate_full_round(n).await.unwrap() }))
        });

        // v7.5 Upgrade: HotStuff + BLS12 (O(n) message complexity)
        if n <= 500 { // Cap at 500 to keep CI under 1 hour
            group.bench_with_input(BenchmarkId::new("HotStuff_v75", n), &n, |b, &n| {
                b.iter(|| rt.block_on(async { HotStuffNode::simulate_full_round(n).await.unwrap() }))
            });
        }
    }
    group.finish();
}

criterion_group!(benches, benchmark_consensus_scaling);
criterion_main!(benches);
