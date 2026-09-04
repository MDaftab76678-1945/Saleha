provider "aws" {
  region = "us-east-1"
}

# 1. Secure VPC
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  name   = "nexus-vpc"
  cidr   = "10.0.0.0/16"
  azs    = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  enable_nat_gateway = true
}

# 2. Managed PostgreSQL (Production Grade)
resource "aws_db_instance" "nexus_db" {
  identifier        = "nexus-postgres"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = "db.t3.medium"
  allocated_storage = 20
  db_name           = "nexus_db"
  username          = "nexus_admin"
  password          = data.aws_secretsmanager_secret_version.db_creds.secret_string # From Secrets Manager
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.nexus_db_subnet.name
  skip_final_snapshot    = true # Set to false in prod
}

# 3. EKS Cluster (For Next.js + Rust FHE Nodes)
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  cluster_name    = "nexus-cluster"
  cluster_version = "1.28"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  
  eks_managed_node_groups = {
    general = {
      min_size     = 2
      max_size     = 5
      desired_size = 2
      instance_types = ["m5.large"]
    }
  }
}
