variable "namespace" { type = string }

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  namespace  = var.namespace
  create_namespace = true

  set { name = "installCRDs"; value = true }
}
