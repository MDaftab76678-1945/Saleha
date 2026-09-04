use serde::{Serialize, Deserialize};

// एक ट्रांजैक्शन अब केवल टोकन ट्रांसफर नहीं, बल्कि एक 'संज्ञानात्मक कार्य' है
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CognitiveTransaction {
    pub agent_did: String,          // एजेंट की विकेंद्रीकृत पहचान
    pub nonce: u64,
    pub zkml_proof: Vec<u8>,        // एजेंट के कार्य का ZK प्रूफ
    pub causal_outcome_hash: [u8; 32], // काउंटरफैक्चुअल सिमुलेशन का हैश
    pub encrypted_payload: Vec<u8>, // FHE से एनक्रिप्टेड डेटा (पेमेंट या मेमोरी)
    pub gas_limit: u64,             // कम्प्यूट लिमिट
}

// पारंपरिक ब्लॉक की जगह 'कॉग्निटिव बैच' (DAG Node)
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CognitiveBlock {
    pub height: u64,
    pub timestamp: u64,
    pub proposer_did: String,       // ब्लॉक प्रपोज़ करने वाला एजेंट/वैलिडेटर
    
    // 5-लेयर पाइपलाइन के रूट्स (Merkle Roots)
    pub zkml_aggregate_proof: Vec<u8>, // सभी ट्रांजैक्शन्स के ZK प्रूफ्स का एग्रीगेट प्रूफ
    pub causal_state_root: [u8; 32],   // कॉज़ल सिमुलेशन का स्टेट रूट
    pub fhe_state_root: [u8; 32],      // एनक्रिप्टेड वर्ल्ड स्टेट का रूट
    
    pub transactions: Vec<CognitiveTransaction>,
    
    // PoVC कंसंसेस के लिए वैलिडेटर्स के सिग्नेचर्स
    pub validator_signatures: Vec<Vec<u8>>, 
}
