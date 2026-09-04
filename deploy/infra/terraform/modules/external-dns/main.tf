variable "namespace" { type = string }
variable "domain_filter" { type = string }

resource "helm_release" "external_dns" {
  name       = "external-dns"
  repository = "https://kubernetes-sigs.github.io/external-dns/"
  chart      = "external-dns"
  namespace  = var.namespace
  create_namespace = true

  set { name = "domainFilters[0]"; value = var.domain_filter }
  set { name = "provider"; value = "aws" }
}
