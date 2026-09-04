variable "environment" { type = string }
variable "db_name" { type = string }
variable "db_username" { type = string; sensitive = true }
variable "db_password" { type = string; sensitive = true }
variable "db_instance_class" { type = string }
variable "allocated_storage" { type = number }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_cidrs" { type = list(string) }
variable "multi_az" { type = bool }
variable "backup_retention" { type = number }
