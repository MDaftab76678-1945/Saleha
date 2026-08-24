---
id: "agent_cloud_architect"
name: "Principal Cloud Solutions Architect"
type: "agent_profile"
version: "2.0.0"
---

# Principal Cloud Solutions Architect Specification

## 1. Enterprise Multi-Region Terraform Architecture
```hcl
module "vpc_primary" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.0"

  name = "prod-vpc-us-east-1"
  cidr = "10.100.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.100.1.0/24", "10.100.2.0/24", "10.100.3.0/24"]
  public_subnets  = ["10.100.101.0/24", "10.100.102.0/24", "10.100.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true
  enable_dns_hostnames   = true
}
```
