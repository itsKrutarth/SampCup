# The API: one Lambda function (FastAPI through Mangum) behind a function URL.
# Only CloudFront can use it: CloudFront adds a secret header the app checks.

# The log group belongs to infra/foundation, so a teardown keeps the logs.
data "aws_cloudwatch_log_group" "api" {
  name = "/aws/lambda/${local.name}-api"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# Least privilege: this table, and this function's own log group.
data "aws_iam_policy_document" "api" {
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchWriteItem",
      "dynamodb:ConditionCheckItem",
    ]
    resources = [aws_dynamodb_table.main.arn]
  }
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${data.aws_cloudwatch_log_group.api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "${local.name}-api"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

resource "random_password" "origin_secret" {
  length  = 48
  special = false
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  handler          = "app.lambda_handler.handler"
  runtime          = "python3.12"
  architectures    = ["arm64"] # Graviton: cheaper per millisecond
  filename         = var.lambda_zip
  source_code_hash = filebase64sha256(var.lambda_zip)
  # 1769 MB is one full vCPU. Requests are CPU-bound (parsing DynamoDB replies), so they run
  # ~3x faster than at 512 MB for the same GB-seconds bill, and the account's limit of 10
  # requests at once goes ~3x further (load test, 2026-11-18).
  memory_size = 1769
  timeout     = 15

  environment {
    variables = {
      APP_ENV       = "production"
      TABLE_NAME    = aws_dynamodb_table.main.name
      ORIGIN_SECRET = random_password.origin_secret.result
    }
  }

  logging_config {
    log_format = "Text" # the app already writes one JSON line per request
    log_group  = data.aws_cloudwatch_log_group.api.name
  }

  depends_on = [aws_iam_role_policy.api]
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "function_url" {
  statement_id           = "AllowFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

