#!/usr/bin/env bash
# k8s/argocd/bootstrap.sh
# One-time ArgoCD installation + MUKTI bootstrap
set -euo pipefail

ARGO_NS="argocd"
REPO_URL="https://github.com/mukti-foundation/mukti"

echo "🚀 Installing ArgoCD..."
kubectl create namespace "$ARGO_NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n "$ARGO_NS" \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

echo "⏳ Waiting for ArgoCD to be ready..."
kubectl rollout status deployment/argocd-server -n "$ARGO_NS" --timeout=300s

echo "🔐 Fetching initial admin password..."
sleep 10
ARGO_PWD=$(kubectl -n "$ARGO_NS" get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)
echo "Admin password: $ARGO_PWD (change this immediately)"

echo "📦 Bootstrapping MUKTI app-of-apps..."
kubectl apply -f k8s/argocd/project.yaml
kubectl apply -f k8s/argocd/app-of-apps.yaml

echo "✅ Bootstrap complete. ArgoCD will now sync:"
echo "   - mukti-api"
echo "   - mukti-monitoring"
echo ""
echo "Next: expose argocd-server via ingress and change admin password."
