#!/usr/bin/env bash
# k8s/chaos/run-replication-chaos.sh
# Orchestrates: k6 replication-lag load test + mid-test replica kill.
set -euo pipefail

# ── Config ──
WRITER_URL="${WRITER_URL:-https://api-us.mukti.ai}"
READER_URL="${READER_URL:-https://api-eu.mukti.ai}"
REPLTEST_TOKEN="${REPLTEST_TOKEN:-}"
READER_CONTEXT="${READER_CONTEXT:-mukti-eu-west-1}"
STS="${STS:-mukti-postgres}"
RESULTS_DIR="loadtest-results/repl-chaos/$(date +%Y%m%d_%H%M%S)"

STABILIZE_S=60     # load stabilizes before chaos
DOWN_S=120         # replica stays down
mkdir -p "$RESULTS_DIR"

echo "═══════════════════════════════════════════"
echo "  Replication Chaos: kill replica mid-test"
echo "  Writer: $WRITER_URL"
echo "  Reader: $READER_URL ($READER_CONTEXT)"
echo "═══════════════════════════════════════════"

cleanup() {
    echo "🧹 Ensuring replica is restored..."
    kubectl --context "$READER_CONTEXT" scale statefulset "$STS" \
        -n mukti --replicas=1 || true
}
trap cleanup EXIT

# 1. Start replication-lag k6 test in background (10 min)
echo "▶ Starting replication-lag k6 test..."
k6 run -e REPLTEST_TOKEN="$REPLTEST_TOKEN" \
    --out json="$RESULTS_DIR/replication-lag.ndjson" \
    loadtest/scenarios/multi-region/replication-lag.js \
    > "$RESULTS_DIR/replication-lag.log" 2>&1 &
K6_PID=$!

# 2. Let load stabilize
echo "⏳ Stabilizing ${STABILIZE_S}s..."
sleep "$STABILIZE_S"

# 3. KILL THE REPLICA
echo "💥 Scaling $STS to 0 in $READER_CONTEXT..."
kubectl --context "$READER_CONTEXT" scale statefulset "$STS" -n mukti --replicas=0

echo "⏳ Replica down for ${DOWN_S}s (k6 keeps measuring)..."
sleep "$DOWN_S"

# 4. Restore replica (trap also guarantees this)
echo "🔄 Restoring replica..."
kubectl --context "$READER_CONTEXT" scale statefulset "$STS" -n mukti --replicas=1

# 5. Wait for k6 to finish and report
wait $K6_PID || echo "⚠️ k6 reported threshold failures (expected during outage)"

echo ""
echo "✅ Chaos run complete. Results: $RESULTS_DIR"
echo ""
grep -A6 "REPLICATION LAG TEST" "$RESULTS_DIR/replication-lag.log" || true
