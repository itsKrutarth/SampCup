# Long-lived pieces that stay when the app stack is torn down:
#   - the Route 53 hosted zone for the domain (its nameservers are entered at Namecheap once)
#   - the HTTPS certificate, validated through that zone
#   - the API's log group, so a teardown never deletes the logs (kept 30 days; pennies)
# Apply once:  infra/foundation.sh apply      (about $0.50 a month for the zone)

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }

  # Bucket passed at init (it includes the account id): see infra/foundation.sh.
  backend "s3" {
    key          = "foundation/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1" # CloudFront certificates must be in us-east-1
  default_tags {
    tags = {
      Project   = "sampcup"
      Component = "foundation"
      ManagedBy = "terraform"
    }
  }
}

variable "domain_name" {
  type    = string
  default = "sampcup.com"
}

resource "aws_route53_zone" "main" {
  name    = var.domain_name
  comment = "SampCup public DNS (registered at Namecheap, nameservers point here)"
}

resource "aws_acm_certificate" "site" {
  domain_name               = var.domain_name
  subject_alternative_names = ["www.${var.domain_name}"]
  validation_method         = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

# ACM checks these records and issues the certificate once Namecheap points at Route 53.
resource "aws_route53_record" "validation" {
  for_each = {
    for o in aws_acm_certificate.site.domain_validation_options : o.domain_name => o
  }
  zone_id         = aws_route53_zone.main.zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 300
  allow_overwrite = true
}

output "name_servers" {
  description = "Enter these four at Namecheap: Domain List -> sampcup.com -> Nameservers -> Custom DNS."
  value       = aws_route53_zone.main.name_servers
}

output "certificate_status" {
  value = aws_acm_certificate.site.status
}

# The API's logs (the app stack's Lambda writes here). They live in this layer so that
# infra/destroy.sh never deletes them: after a teardown the past days can still be read.
variable "api_log_group" {
  type    = string
  default = "/aws/lambda/sampcup-prod-api"
}

variable "log_retention_days" {
  description = "How long API logs are kept."
  type        = number
  default     = 30
}

resource "aws_cloudwatch_log_group" "api" {
  name              = var.api_log_group
  retention_in_days = var.log_retention_days
}

# One-time move (2026-11-22): adopt the log group the app stack created, logs and all.
# Delete this block once applied.
import {
  to = aws_cloudwatch_log_group.api
  id = "/aws/lambda/sampcup-prod-api"
}

output "api_log_group" {
  value = aws_cloudwatch_log_group.api.name
}
