# =============================================================================
# MUKTI Ecosystem - Root Terraform Configuration
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }

  # Remote state backend (S3 + DynamoDB)
  backend "s3" {
    bucket         = "mukti-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "mukti-terraform-locks"
  }
}

# =============================================================================
# PROVIDERS
# =============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "mukti"
      Environment = var.environment
      ManagedBy   = "terraform"
      Team        = "platform"
    }
  }
}

# =============================================================================
# DATA SOURCES
# =============================================================================

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# =============================================================================
# MODULES
# =============================================================================

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 3)
  
  private_subnets    = var.private_subnets
  public_subnets     = var.public_subnets
  database_subnets   = var.database_subnets

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  environment        = var.environment
  cluster_name       = "mukti-${var.environment}"
  cluster_version    = var.eks_cluster_version
  
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  node_instance_types = var.eks_node_instance_types
  node_desired_size   = var.eks_node_desired_size
  node_min_size       = var.eks_node_min_size
  node_max_size       = var.eks_node_max_size

  depends_on = [module.vpc]
}

# RDS Module (PostgreSQL)
module "rds" {
  source = "./modules/rds"

  environment        = var.environment
  db_name            = "nexus_omni"
  db_username        = var.db_username
  db_password        = var.db_password
  db_instance_class  = var.db_instance_class
  allocated_storage  = var.db_allocated_storage

  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.database_subnet_ids
  allowed_cidrs      = [module.vpc.vpc_cidr]

  multi_az           = var.environment == "production"
  backup_retention   = var.environment == "production" ? 30 : 7

  depends_on = [module.vpc]
}

# ElastiCache Module (Redis)
module "elasticache" {
  source = "./modules/elasticache"

  environment        = var.environment
  cluster_name       = "mukti-redis-${var.environment}"
  node_type          = var.redis_node_type
  num_cache_nodes    = var.environment == "production" ? 3 : 1

  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  allowed_cidrs      = [module.vpc.vpc_cidr]

  depends_on = [module.vpc]
}

# Qdrant on EKS (via Helm)
module "qdrant" {
  source = "./modules/qdrant"

  environment    = var.environment
  namespace      = "nexus-${var.environment}"
  storage_size   = var.environment == "production" ? "100Gi" : "20Gi"
  replica_count  = var.environment == "production" ? 3 : 1

  depends_on = [module.eks]
}
