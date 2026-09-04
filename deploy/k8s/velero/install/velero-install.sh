#!/bin/bash
# ================================================================
# MUKTI - Velero Installation Script
# Production-grade backup and disaster recovery setup
# ================================================================
set -euo pipefail

# Configuration
VELERO_VERSION="v1.13.0"
VELERO_NAMESPACE="velero"
BUCKET_NAME="${VELERO_BUCKET:-mukti-backups}"
AWS_REGION="${AWS_REGION:-us-east-1}"
S3_URL="${S3_URL:-https://s3.${AWS_REGION}.amazonaws.com}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

echo "============================================"
echo "MUKTI Velero Installation"
echo "Version: ${VELERO_VERSION}"
echo "Bucket: ${BUCKET_NAME}"
echo "Region: ${AWS_REGION}"
echo "============================================"

# Step 1: Install Velero CLI
echo "[1/6] Installing Velero CLI..."
if ! command -v velero &> /dev/null; then
    curl -sSL "https://github.com/vmware-tanzu/velero/releases/download/${VELERO_VERSION}/velero-${VELERO_VERSION}-linux-amd64.tar.gz" -o /tmp/velero.tar.gz
    tar -xzf /tmp/velero.tar.gz -C /tmp
    sudo mv "/tmp/velero-${VELERO_VERSION}-linux-amd64/velero" /usr/local/bin/velero
    chmod +x /usr/local/bin/velero
    rm -rf /tmp/velero*
    echo "✅ Velero CLI installed: $(velero version --client-only)"
else
    echo "✅ Velero CLI already installed: $(velero version --client-only)"
fi

# Step 2: Create namespace
echo "[2/6] Creating namespace..."
kubectl create namespace "${VELERO_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Step 3: Create credentials secret
echo "[3/6] Creating credentials secret..."
cat > /tmp/credentials-velero <<EOF
[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
EOF

kubectl create secret generic "cloud-credentials" \
    --namespace "${VELERO_NAMESPACE}" \
    --from-file=cloud=/tmp/credentials-velero \
    --dry-run=client -o yaml | kubectl apply -f -
rm -f /tmp/credentials-velero

# Step 4: Install Velero server
echo "[4/6] Installing Velero server..."
velero install \
    --provider aws \
    --plugins velero/velero-plugin-for-aws:v1.9.0 \
    --bucket "${BUCKET_NAME}" \
    --backup-location-config "region=${AWS_REGION},s3Url=${S3_URL}" \
    --snapshot-location-config "region=${AWS_REGION}" \
    --secret-file /tmp/credentials-velero \
    --namespace "${VELERO_NAMESPACE}" \
    --use-volume-snapshots=true \
    --default-backup-ttl "720h"

# Step 5: Wait for Velero deployment
echo "[5/6] Waiting for Velero deployment..."
kubectl rollout status deployment/velero -n "${VELERO_NAMESPACE}" --timeout=300s

# Step 6: Verify installation
echo "[6/6] Verifying installation..."
velero backup-location get
velero snapshot-location get

echo ""
echo "============================================"
echo "✅ Velero installation complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Create backup schedule: kubectl apply -f k8s/velero/schedules/"
echo "  2. Test backup: velero backup create test-backup --wait"
echo "  3. Verify: velero backup describe test-backup"
echo "============================================"
