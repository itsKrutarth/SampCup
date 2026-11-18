terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }

  # The bucket name includes the account id, so it is passed at init time:
  #   terraform init -backend-config="bucket=sampcup-tfstate-<account-id>"
  # (infra/deploy.sh does this.)
  backend "s3" {
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  # us-east-1: CloudFront certificates must live here, and it is the cheapest region.
  region = "us-east-1"
  default_tags {
    tags = {
      Project     = "sampcup"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name = "sampcup-${var.environment}"
}
