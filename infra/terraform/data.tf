# One DynamoDB table holds the whole tournament. On-demand billing: no charge while idle,
# and storage stays far inside the 25 GB free tier.
resource "aws_dynamodb_table" "main" {
  name                        = local.name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "pk"
  range_key                   = "sk"
  deletion_protection_enabled = var.protect_data

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  # Logins and rate-limit counters carry a "ttl" time; DynamoDB deletes them for free.
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Restore to any second of the last 35 days. Billed by table size (well under 1 MB).
  point_in_time_recovery {
    enabled = true
  }
}
