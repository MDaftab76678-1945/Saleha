variable "environment" { type = string }
variable "namespace" { type = string }
variable "storage_size" { type = string }
variable "replica_count" { type = number }

resource "helm_release" "qdrant" {
  name       = "qdrant"
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  namespace  = var.namespace
  create_namespace = true

  set { name = "replicaCount"; value = var.replica_count }
  set { name = "persistence.size"; value = var.storage_size }
}
