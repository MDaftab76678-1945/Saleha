-- Create table for FHE circuit cache
CREATE TABLE IF NOT EXISTS fhe_circuit_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_name VARCHAR(255) NOT NULL,
    circuit_hash VARCHAR(64) NOT NULL UNIQUE,
    compiled_circuit BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for fast lookups
CREATE INDEX idx_circuit_hash ON fhe_circuit_cache(circuit_hash);

-- Create table for proof audit trail
CREATE TABLE IF NOT EXISTS zk_proof_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(255) NOT NULL,
    agent_did VARCHAR(255) NOT NULL,
    proof_hash VARCHAR(64) NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_proof_request ON zk_proof_audit(request_id);
CREATE INDEX idx_proof_agent ON zk_proof_audit(agent_did);
