terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

locals {
  platform_name = "model-observability-incident-platform"
  node_pools    = ["system", "observability-on-demand", "batch-checks"]
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.platform_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access = true
  enable_irsa                    = true

  cluster_compute_config = {
    enabled    = true
    node_pools = local.node_pools
  }

  tags = {
    Project     = local.platform_name
    Environment = var.environment
  }
}

resource "aws_s3_bucket" "telemetry" {
  bucket = "${local.platform_name}-${var.environment}-telemetry"
}

resource "aws_s3_bucket_versioning" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  versioning_configuration {
    status = "Enabled"
  }
}
