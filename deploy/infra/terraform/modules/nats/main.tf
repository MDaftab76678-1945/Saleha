variable "environment" { type = string }
variable "namespace" { type = string }

resource "helm_release" "nats" {
  name       = "nats"
  repository = "https://nats-io.github.io/k8s/helm/charts/"
  chart      = "nats"
  namespace  = var.namespace

  set { name = "jetstream.enabled"; value = true }
  set { name = "jetstream.fileStorage.enabled"; value = true }
  set { name = "jetstream.fileStorage.size"; value = "10Gi" }
}
