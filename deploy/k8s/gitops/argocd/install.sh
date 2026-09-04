#!/bin/bash
# ================================================================
# MUKTI - ArgoCD Installation Script
# Production GitOps setup
# ================================================================
set -euo pipefail

ARGOCD_NAMESPACE="argocd"
ARGOCD_VERSION="v2.10.0"
DOMAIN="argocd.mukti.ai"

echo "============================================"
echo "MUKTI ArgoCD Installation"
echo "Version: ${ARGOCD_VERSION}"
echo "Domain: ${DOMAIN}"
echo "============================================"

# Step 1: Create namespace
echo "[1/7] Creating namespace..."
kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Step 2: Install ArgoCD
echo "[2/7] Installing ArgoCD..."
kubectl apply -n "${ARGOCD_NAMESPACE}" -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

# Wait for deployment
echo "[3/7] Waiting for ArgoCD deployment..."
kubectl rollout status deployment/argocd-server -n "${ARGOCD_NAMESPACE}" --timeout=300s

# Step 4: Patch for LoadBalancer
echo "[4/7] Configuring LoadBalancer..."
kubectl patch svc argocd-server -n "${ARGOCD_NAMESPACE}" -p '{"spec": {"type": "LoadBalancer"}}'

# Step 5: Configure TLS
echo "[5/7] Configuring TLS..."
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server-ingress
  namespace: ${ARGOCD_NAMESPACE}
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123456789:certificate/xxx
    alb.ingress.kubernetes.io/backend-protocol: HTTPS
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
spec:
  ingressClassName: alb
  tls:
    - hosts:
        - ${DOMAIN}
      secretName: argocd-tls
  rules:
    - host: ${DOMAIN}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 443
EOF

# Step 6: Configure RBAC
echo "[6/7] Configuring RBAC..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: ${ARGOCD_NAMESPACE}
data:
  policy.csv: |
    g, mukti-admins, role:admin
    g, mukti-developers, role:readonly
    g, mukti-ops, role:admin
  policy.default: role:readonly
EOF

# Step 7: Get admin password
echo "[7/7] Getting admin password..."
sleep 30
ARGOCD_ADMIN_PASSWORD=$(kubectl -n "${ARGOCD_NAMESPACE}" get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

echo ""
echo "============================================"
echo "✅ ArgoCD installation complete!"
echo "============================================"
echo "URL: https://${DOMAIN}"
echo "Username: admin"
echo "Password: ${ARGOCD_ADMIN_PASSWORD}"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Login to ArgoCD UI"
echo "  2. Add Git repository"
echo "  3. Apply Application manifests"
echo "  4. Configure RBAC"
echo "============================================"
