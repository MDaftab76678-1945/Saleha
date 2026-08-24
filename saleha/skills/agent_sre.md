---
id: "agent_sre"
name: "Principal Site Reliability Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Principal Site Reliability Engineer Specification

## 1. Prometheus Multi-Window SLO Burn-Rate Alerting
```yaml
groups:
  - name: latency-slo-alerts
    rules:
      - alert: HighHttpErrorRateBurnRate
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total[5m]))
          ) > (14.4 * (1 - 0.999))
        for: 2m
        labels:
          severity: critical
          tier: platform
        annotations:
          summary: "Production HTTP 5xx Burn Rate Exceeds Critical Threshold"
```

