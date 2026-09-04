use criterion::{criterion_group, criterion_main, Criterion, black_box};
use nexus_safety::{MemoryInterpProbe, SafetyRail};

fn benchmark_memory_probe_overhead(c: &mut Criterion) {
    let mut group = c.benchmark_group("Safety_Overhead_v75");
    let probe = MemoryInterpProbe::from_stub_weights(0.85);
    let activations = vec![0.05f32; 4096]; // Standard 4096-dim hidden state

    group.bench_function("Memory_Retrieval_Baseline", |b| {
        b.iter(|| black_box(hnsw_search_stub(&activations)))
    });

    group.bench_function("Memory_Retrieval_With_SAE_Probe", |b| {
        b.iter(|| {
            black_box(hnsw_search_stub(&activations));
            black_box(futures::executor::block_on(probe.probe_retrieval(&activations)));
        })
    });
    group.finish();
}

fn hnsw_search_stub(_vec: &[f32]) -> Vec<u64> {
    // Simulates ~15ms HNSW episodic memory search
    std::thread::sleep(std::time::Duration::from_micros(150)); 
    vec![1, 2, 3]
}

criterion_group!(benches, benchmark_memory_probe_overhead);
criterion_main!(benches);
