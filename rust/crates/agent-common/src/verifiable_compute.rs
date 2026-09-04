use halo2_proofs::{
    plonk::{Proof, VerifyingKey},
    poly::commitment::Params,
};
use serde::{Deserialize, Serialize};

// यह स्ट्रक्चर एजेंट के आउटपुट और उसके ज़ीरो-नॉलेज प्रूफ को बाइंड करता है
#[derive(Serialize, Deserialize, Debug)]
pub struct VerifiableExecutionResult {
    pub agent_did: String,
    pub task_id: String,
    
    // पब्लिक इनपुट्स (जैसे टास्क का हैश, बिना असली प्रॉम्प्ट रिवील किए)
    pub public_inputs: Vec<[u8; 32]>, 
    
    // पब्लिक आउटपुट्स (एजेंट का फाइनल रिस्पॉन्स)
    pub public_outputs: Vec<f32>,     
    
    // ZK Proof (Halo2 KZG प्रूफ बाइट्स)
    pub zk_proof_bytes: Vec<u8>,      
    
    // मॉडल का कमिटमेंट (यह साबित करता है कि कौन सा ONNX मॉडल रन हुआ)
    pub model_commitment: [u8; 32],   
}
