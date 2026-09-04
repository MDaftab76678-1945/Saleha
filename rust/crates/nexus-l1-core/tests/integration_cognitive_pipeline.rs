use nexus_l1_core::primitives::{CognitiveTransaction, CognitiveBlock};
use nexus_l1_core::consensus::povc::PovcConsensusEngine;
use nexus_l1_core::state::fhe_machine::{FheStateTransitioner, EncryptedWorldState};
use nexus_l1_economics::synapse_channel::SynapseM2MEngine;
use nexus_l1_economics::pricing_engine::DynamicPricingEngine;

/// टेस्ट 1: पूरी कॉग्निटिव पाइपलाइन E2E
#[tokio::test]
async fn test_full_cognitive_pipeline_e2e() {
    // 1. एजेंट का DID और टास्क तैयार करना
    let agent_did = "did:nexus:agent:test_001".to_string();
    let task_payload = b"Execute autonomous market analysis".to_vec();

    // 2. SNN रिफ्लेक्स चेक
    let snn = nexus_l1_core::reflex::SnnEngine::new(128);
    let reflex_state = snn.check_safety_reflex(&task_payload).await.unwrap();
    assert!(reflex_state.is_safe, "SNN should pass safe inputs");
    assert!(reflex_state.threat_vector < 0.75);

    // 3. GNN स्वार्म फॉर्मेशन
    let gnn = nexus_l1_core::swarm::GnnEngine::new(vec![
        nexus_l1_core::primitives::AgentNode {
            did: agent_did.clone(),
            role: "analyst".to_string(),
            compute_capacity: 0.9,
        },
    ]);
    let topology = gnn.form_dynamic_topology(0.5).await.unwrap();
    assert!(!topology.nodes.is_empty(), "Swarm should have at least one node");

    // 4. कॉज़ल सिमुलेशन
    let causal = nexus_l1_core::causal::CausalEngine::new();
    let outcome = causal.simulate_counterfactuals(&topology).await.unwrap();
    assert!(outcome.expected_utility > 0.0, "Utility should be positive");

    // 5. zkML प्रूफ (सिमुलेशन)
    let zkml = nexus_l1_core::zkml::ZkmlEngine::new();
    let proof = zkml.generate_proof(&task_payload).await.unwrap();
    assert!(!proof.proof_bytes.is_empty(), "ZK Proof should not be empty");

    println!("✅ Full cognitive pipeline E2E test PASSED");
}

/// टेस्ट 2: FHE स्टेट ट्रांजिशन (डबल-स्पेंड रोकना)
#[tokio::test]
async fn test_fhe_state_prevents_double_spend() {
    let transitioner = FheStateTransitioner::new();
    let mut state = EncryptedWorldState::new();
    
    let tx1 = CognitiveTransaction {
        agent_did: "did:nexus:agent:001".to_string(),
        nonce: 1,
        zkml_proof: vec![1, 2, 3],
        causal_outcome_hash: [0u8; 32],
        encrypted_payload: transitioner.fhe_encrypt(500),
        gas_limit: 1000,
    };

    // पहला ट्रांजैक्शन अप्लाई करना
    transitioner.apply_transaction(&mut state, &tx1).unwrap();
    
    // नॉन-रीप्ले: वही नॉन-स दोबारा अप्लाई नहीं होना चाहिए
    let result = transitioner.apply_transaction(&mut state, &tx1);
    assert!(result.is_err(), "Double-spend (replay) should be rejected");

    println!("✅ FHE double-spend prevention test PASSED");
}

/// टेस्ट 3: PoVC कंसंसेस (मूर्ख ब्लॉक को रिजेक्ट करना)
#[tokio::test]
async fn test_povc_rejects_low_utility_block() {
    let consensus = PovcConsensusEngine::new(0.8); // उच्च थ्रेसहोल्ड
    
    let bad_block = CognitiveBlock {
        height: 1,
        timestamp: 1700000000,
        proposer_did: "did:nexus:validator:001".to_string(),
        zkml_aggregate_proof: vec![0u8; 256],
        causal_state_root: [0u8; 32],
        fhe_state_root: [0u8; 32],
        transactions: vec![
            CognitiveTransaction {
                agent_did: "did:nexus:agent:bad".to_string(),
                nonce: 1,
                zkml_proof: vec![],
                causal_outcome_hash: [0u8; 32],
                encrypted_payload: vec![],
                gas_limit: 100,
            }
        ],
        validator_signatures: vec![vec![0u8; 48]],
    };

    let result = consensus.validate_block(&bad_block).await;
    assert!(result.is_err(), "PoVC should reject blocks with low causal utility");

    println!("✅ PoVC consensus rejection test PASSED");
}

/// टेस्ट 4: सिनैप्स M2M चैनल (माइक्रो-पेमेंट्स)
#[tokio::test]
async fn test_synapse_channel_micro_payments() {
    let mut engine = SynapseM2MEngine::new();
    
    let channel_id = engine.open_channel(
        "did:nexus:agent:A", 
        "did:nexus:agent:B", 
        10000, 10000
    ).await.unwrap();

    // 100 माइक्रो-पेमेंट्स करना
    for _ in 0..100 {
        engine.execute_micro_payment(&channel_id, true, 10).await.unwrap();
    }

    // सेटलमेंट
    let (bal_a, bal_b) = engine.settle_and_close_channel(&channel_id).await.unwrap();
    
    // A ने 1000 भेजे, इसलिए A का कम और B का अधिक होना चाहिए
    assert!(bal_a < 10000, "Agent A balance should decrease");
    assert!(bal_b > 10000, "Agent B balance should increase");
    assert_eq!(bal_a + bal_b, 20000, "Total supply should be conserved");

    println!("✅ Synapse channel 100 micro-payments test PASSED");
}

/// टेस्ट 5: डायनामिक प्राइसिंग (जटिल टास्क = अधिक लागत)
#[test]
fn test_dynamic_pricing_complexity() {
    let pricing = DynamicPricingEngine::new();
    
    let simple_reflex = nexus_l1_core::primitives::ReflexState {
        is_safe: true,
        threat_vector: 0.1,
        spike_trains: vec![vec![1, 0, 1]],
    };
    
    let complex_reflex = nexus_l1_core::primitives::ReflexState {
        is_safe: true,
        threat_vector: 0.1,
        spike_trains: vec![vec![1; 1000]], // 1000x अधिक स्पिक्स
    };

    let simple_topology = nexus_l1_core::primitives::SwarmTopology {
        nodes: vec![],
        edges: vec![],
    };
    
    let complex_topology = nexus_l1_core::primitives::SwarmTopology {
        nodes: (0..50).map(|i| nexus_l1_core::primitives::AgentNode {
            did: format!("agent_{}", i),
            role: "worker".to_string(),
            compute_capacity: 0.5,
        }).collect(),
        edges: vec![],
    };

    let simple_proof = nexus_l1_core::primitives::ZkProof {
        proof_bytes: vec![0u8; 100],
        public_inputs: vec![],
        public_outputs: vec![],
    };
    
    let complex_proof = nexus_l1_core::primitives::ZkProof {
        proof_bytes: vec![0u8; 100_000], // 1000x बड़ा प्रूफ
        public_inputs: vec![],
        public_outputs: vec![],
    };

    let simple_cost = pricing.calculate_task_cost(&simple_reflex, &simple_topology, &simple_proof, 1).unwrap();
    let complex_cost = pricing.calculate_task_cost(&complex_reflex, &complex_topology, &complex_proof, 100).unwrap();

    assert!(complex_cost > simple_cost * 10, "Complex tasks should cost significantly more");

    println!("✅ Dynamic pricing complexity test PASSED (Simple: {} ECU, Complex: {} ECU)", simple_cost, complex_cost);
}
