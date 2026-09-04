use criterion::{criterion_group, criterion_main, Criterion, Throughput};
use nexus_consensus::pbft::PbftNode;
use tokio::runtime::Runtime;

fn pbft_throughput_benchmark(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let mut group = c.benchmark_group("PBFT_Consensus");
    
    for node_count in [4, 10, 50, 100, 200].iter() {
        group.throughput(Throughput::Elements(*node_count as u64));
        group.bench_with_input(
            criterion::BenchmarkId::from_parameter(node_count), 
            node_count, 
            |b, &n| {
                b.iter(|| {
                    rt.block_on(async {
                        PbftNode::simulate_round(n).await
                    })
                });
            }
        );
    }
    group.finish();
}

criterion_group!(benches, pbft_throughput_benchmark);
criterion_main!(benches);
