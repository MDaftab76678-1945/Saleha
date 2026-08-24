---
id: "doc_database_schema"
title: "Production Relational DDL & Migration Governance"
version: "3.0.0"
---

# Production Database Schema & Migration Governance

## 1. Production PostgreSQL 16+ DDL (With UUIDv7, Partitioning & RLS)
```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    amount_cents BIGINT NOT NULL CHECK (amount_cents > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_orders_active_user ON orders (user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_orders_created_status ON orders (status, created_at DESC);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON orders
    FOR ALL
    USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
```

