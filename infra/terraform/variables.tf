variable "environment" {
  description = "Name used in every resource name."
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "The public site's domain (DNS in Route 53, see infra/foundation)."
  type        = string
  default     = "sampcup.com"
}

variable "enable_custom_domain" {
  description = "Serve the domain. infra/deploy.sh turns this on once the certificate is issued."
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Where alarms are emailed (confirm the subscription email AWS sends). Empty = no email."
  type        = string
  default     = ""
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
