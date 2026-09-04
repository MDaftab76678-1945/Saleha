#!/bin/bash
# ================================================================
# MUKTI - Disaster Recovery Drill Script
# Automated DR testing - run weekly
# ================================================================
set -euo pipefail

NAMESPACE="mukti-dr-test"
BACKUP_NAME="mukti-dr-drill-$(date +%Y%m%d-%H%M%S)"
RESTORE_NAME="mukti-dr-restore-$(date +%Y%m%d-%H%M%S)"
TIMEOUT=900  # 15 minutes

echo "============================================"
echo "MUKTI Disaster Recovery Drill"
echo "Start: $(date -u)"
echo "============================================"

cleanup() {
    echo "[CLEANUP] Removing DR test namespace..."
    kubectl delete namespace "${NAMESPACE}" --ignore-not-found=true
    velero restore delete "${RESTORE_NAME}" -n velero --confirm || true
    velero backup delete "${BACKUP_NAME}" -n velero --confirm || true
}

# Cleanup on exit
trap cleanup EXIT

# Step 1: Create backup
echo "[1/6] Creating backup..."
velero backup create "${BACKUP_NAME}" \
    --include-namespaces mukti,mukti-database \
    --snapshot-volumes \
    --wait

echo "✅ Backup created: ${BACKUP_NAME}"

# Step 2: Verify backup
echo "[2/6] Verifying backup..."
velero backup describe "${BACKUP_NAME}" --details

BACKUP_STATUS=$(velero backup get "${BACKUP_NAME}" -o jsonpath='{.status.phase}')
if [[ "${BACKUP_STATUS}" != "Completed" ]]; then
    echo "❌ Backup failed with status: ${BACKUP_STATUS}"
    exit 1
fi

# Step 3: Create DR test namespace
echo "[3/6] Creating DR test namespace..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Step 4: Restore to test namespace
echo "[4/6] Restoring to test namespace..."
START_TIME=$(date +%s)

velero restore create "${RESTORE_NAME}" \
    --from-backup "${BACKUP_NAME}" \
    --namespace-mappings "mukti:${NAMESPACE},mukti-database:${NAMESPACE}-db" \
    --restore-pvs \
    --wait

END_TIME=$(date +%s)
RESTORE_DURATION=$((END_TIME - START_TIME))

echo "✅ Restore completed in ${RESTORE_DURATION}s"

# Step 5: Verify restored resources
echo "[5/6] Verifying restored resources..."
sleep 30  # Wait for pods to start

# Check deployments
DEPLOYMENT_COUNT=$(kubectl get deployments -n "${NAMESPACE}" --no-headers | wc -l)
RUNNING_PODS=$(kubectl get pods -n "${NAMESPACE}" --field-selector=status.phase=Running --no-headers | wc -l)
TOTAL_PODS=$(kubectl get pods -n "${NAMESPACE}" --no-headers | wc -l)

echo "Deployments: ${DEPLOYMENT_COUNT}"
echo "Running pods: ${RUNNING_PODS}/${TOTAL_PODS}"

# Health check
echo "[6/6] Running health checks..."
HEALTH_CHECK_PASSED=true

# Check if backend is responding
BACKEND_URL=$(kubectl get svc -n "${NAMESPACE}" -l app=mukti-backend -o jsonpath='{.items[0].spec.clusterIP}' 2>/dev/null || echo "")
if [[ -n "${BACKEND_URL}" ]]; then
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "http://${BACKEND_URL}:8000/health" --max-time 30 || echo "000")
    if [[ "${HEALTH_RESPONSE}" == "200" ]]; then
        echo "✅ Backend health check passed"
    else
        echo "❌ Backend health check failed: HTTP ${HEALTH_RESPONSE}"
        HEALTH_CHECK_PASSED=false
    fi
fi

# Generate report
REPORT_FILE="/tmp/mukti-dr-report-$(date +%Y%m%d-%H%M%S).json"
cat > "${REPORT_FILE}" <<EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "backup_name": "${BACKUP_NAME}",
    "backup_status": "${BACKUP_STATUS}",
    "restore_duration_seconds": ${RESTORE_DURATION},
    "deployment_count": ${DEPLOYMENT_COUNT},
    "running_pods": ${RUNNING_PODS},
    "total_pods": ${TOTAL_PODS},
    "health_check_passed": ${HEALTH_CHECK_PASSED},
    "drill_passed": $(if [[ "${HEALTH_CHECK_PASSED}" == "true" && "${RESTORE_DURATION}" -lt ${TIMEOUT} ]]; then echo "true"; else echo "false"; fi)
}
EOF

echo ""
echo "============================================"
echo "DR Drill Report: ${REPORT_FILE}"
echo "============================================"
cat "${REPORT_FILE}"
echo "============================================"

# Cleanup handled by trap
echo ""
echo "✅ DR drill completed!"
