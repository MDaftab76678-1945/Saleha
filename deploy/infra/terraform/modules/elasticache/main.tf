# =============================================================================
# ElastiCache Redis Module
# =============================================================================

variable "environment" { type = string }
variable "cluster_name" { type = string }
variable "node_type" { type = string }
variable "num_cache_nodes" { type = number }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_cidrs" { type = list(string) }

# Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "mukti-${var.environment}-redis-subnet"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "mukti-${var.environment}-redis-subnet-group"
  }
}

# Security Group
resource "aws_security_group" "redis" {
  name_prefix = "mukti-${var.environment}-redis-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
    description = "Redis access from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "mukti-${var.environment}-redis-sg"
  }
}

# Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  name   = "mukti-${var.environment}-redis-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  tags = {
    Name = "mukti-${var.environment}-redis-params"
  }
}

# Replication Group (Cluster Mode)
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = var.cluster_name
  description          = "MUKTI Redis ${var.environment}"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes

  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name

  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.num_cache_nodes > 1

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "Mon:05:00-Mon:06:00"

  apply_immediately = var.environment != "production"

  tags = {
    Name        = var.cluster_name
    Environment = var.environment
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "primary_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "reader_endpoint" {
  value = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "port" {
  value = aws_elasticache_replication_group.main.port
}

output "connection_url" {
  value     = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
  sensitive = true
}
