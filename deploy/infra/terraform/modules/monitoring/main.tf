variable "environment" { type = string }
variable "namespace" { type = string }
variable "grafana_admin_password" { type = string; sensitive = true }

resource "helm_release" "prometheus_stack" {
  name       = "kube-prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = var.namespace
  create_namespace = true

  set { name = "grafana.adminPassword"; value = var.grafana_admin_password }
  set { name = "prometheus.prometheusSpec.retention"; value = "30d" }
}
