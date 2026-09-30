use crate::cognitive_state::{ReflexState, SwarmTopology, ZkProof};
use anyhow::Result;

pub struct DynamicPricingEngine {
    // नेटवर्क कॉन्गेशन के आधार पर ये वेट्स हर ब्लॉक में अपडेट होते हैं
    pub alpha_snn: f64,
    pub beta_gnn: f64,
    pub gamma_zkml: f64,
    pub delta_fhe: f64,
    
    // बेस गैस प्राइस (ECUs में)
    pub base_gas_price: u64, 
}

impl DynamicPricingEngine {
    pub fn new() -> Self {
        Self {
            alpha_snn: 0.01,  // SNN स्पिक्स सस्ते हैं (माइक्रोसेकंड में होते हैं)
            beta_gnn: 0.50,   // GNN रूटिंग मध्यम है (GPU पर होता है)
            gamma_zkml: 5.00, // zkML प्रूफिंग बहुत महंगा है (हेवी कंप्यूट)
            delta_fhe: 10.00, // FHE ऑपरेशन्स सबसे महंगे हैं (मेमोरी इंटेंसिव)
            base_gas_price: 100,
        }
    }

    // किसी भी टास्क की ECU लागत की गणना करना
    pub fn calculate_task_cost(
        &self, 
        reflex: &ReflexState, 
        topology: &SwarmTopology, 
        proof: &ZkProof, 
        fhe_ops_count: u64
    ) -> Result<u64> {
        
        // 1. SNN लोड (स्पिक्स की कुल संख्या)
        let snn_load = reflex.spike_trains.iter().map(|t| t.len()).sum::<usize>() as f64;
        
        // 2. GNN लोड (नोड्स + एज्स)
        let gnn_load = (topology.nodes.len() + topology.edges.len()) as f64;
        
        // 3. zkML लोड (प्रूफ के बाइट्स का साइज़ KB में)
        let zkml_load = (proof.proof_bytes.len() as f64) / 1024.0;
        
        // 4. FHE लोड
        let fhe_load = fhe_ops_count as f64;

        // सूत्र लागू करना
        let dynamic_cost = (self.alpha_snn * snn_load) 
                         + (self.beta_gnn * gnn_load) 
                         + (self.gamma_zkml * zkml_load) 
                         + (self.delta_fhe * fhe_load);

        // कुल लागत = बेस प्राइस + डायनामिक कॉस्ट
        let total_ecu_cost = self.base_gas_price + (dynamic_cost.ceil() as u64);

        Ok(total_ecu_cost)
    }

    // यदि एजेंट का $\Psi$ (Reputation) स्कोर tinggi है, तो उसे डिस्काउंट मिलेगा
    pub fn apply_reputation_discount(&self, base_cost: u64, psi_score: f32) -> u64 {
        // अधिकतम 50% डिस्काउंट
        let discount_multiplier = 1.0 - (psi_score * 0.5).min(0.5);
        (base_cost as f64 * discount_multiplier).ceil() as u64
    }
}
