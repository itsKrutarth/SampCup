output "site_url" {
  description = "The app, before the domain is attached."
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "table_name" {
  value = aws_dynamodb_table.main.name
}

output "log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "dashboard_url" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards/dashboard/${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "certificate_status" {
  value = aws_acm_certificate.site.status
}

output "namecheap_records" {
  description = "Add these at Namecheap (Advanced DNS). Validation first; the site records when the domain is switched on."
  value = concat(
    [for o in aws_acm_certificate.site.domain_validation_options : {
      purpose = "certificate validation for ${o.domain_name}"
      type    = o.resource_record_type
      host    = trimsuffix(trimsuffix(o.resource_record_name, "."), ".${var.domain_name}")
      value   = trimsuffix(o.resource_record_value, ".")
    }],
    [
      { purpose = "site", type = "ALIAS", host = "@", value = aws_cloudfront_distribution.main.domain_name },
      { purpose = "site", type = "CNAME", host = "www", value = aws_cloudfront_distribution.main.domain_name },
    ],
  )
}
