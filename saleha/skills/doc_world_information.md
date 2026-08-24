---
id: "doc_world_information"
title: "Global System Topology, Environment State & Service Registry"
version: "3.0.0"
---

# Global System State & World Information

## 1. Deployment Topology Matrix
| Environment | Kubernetes Cluster | Primary Region | Fallback Region | Datastore Endpoint |
|---|---|---|---|---|
| Development | `k8s-dev-us-east-1` | `us-east-1` | None | `pg-dev.internal:5432` |
| Staging | `k8s-stg-us-east-1` | `us-east-1` | `us-west-2` | `pg-stg.internal:5432` |
| Production | `k8s-prd-global` | `us-east-1` (Active) | `eu-west-1` (Standby) | `aurora-global-cluster` |

## 2. Global Rate Limiting & Gateway Quotas
* **Public Tier (Anonymous):** $60\text{ req/min}$ per IP.
* **Authenticated User Tier:** $600\text{ req/min}$ per User UUID.
* **Enterprise Partner API Tier:** $10,000\text{ req/min}$ per API Key.

