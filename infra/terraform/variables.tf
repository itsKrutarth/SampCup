variable "environment" {
  description = "Name used in every resource name."
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "The public site's domain (DNS stays at Namecheap)."
  type        = string
  default     = "sampcup.com"
}

variable "enable_custom_domain" {
  description = "Attach the domain to CloudFront. Turn on after the certificate's DNS records are in place."
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Where alarms are emailed (confirm the subscription email AWS sends). Empty = no email."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "How long API logs are kept."
  type        = number
  default     = 30
}

variable "lambda_zip" {
  description = "API package built by infra/build.sh."
  type        = string
  default     = "../build/api.zip"
}

variable "site_dir" {
  description = "Built frontend (frontend/dist)."
  type        = string
  default     = "../../frontend/dist"
}

variable "protect_data" {
  description = "Refuse to delete the database. infra/destroy.sh turns this off just before a teardown."
  type        = bool
  default     = true
}
