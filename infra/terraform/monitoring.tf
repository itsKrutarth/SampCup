# Keeping watch: alarms (emailed if alert_email is set) and one dashboard.
# All inside CloudWatch's free allowance (10 alarms, 3 dashboards, 10 custom metrics).

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# The app logs one JSON line per request; count the ones that failed on our side.
resource "aws_cloudwatch_log_metric_filter" "server_errors" {
  name           = "${local.name}-server-errors"
  log_group_name = data.aws_cloudwatch_log_group.api.name
  pattern        = "{ $.status >= 500 }"
  metric_transformation {
    name      = "ServerErrors"
    namespace = "SampCup"
    value     = "1"
  }
}

locals {
  alarms = {
    "api-server-errors" = {
      namespace  = "SampCup"
      metric     = "ServerErrors"
      dimensions = {}
      statistic  = "Sum"
      threshold  = 1
      text       = "The API answered with a server error (5xx). Check the logs."
    }
    "lambda-errors" = {
      namespace  = "AWS/Lambda"
      metric     = "Errors"
      dimensions = { FunctionName = aws_lambda_function.api.function_name }
      statistic  = "Sum"
      threshold  = 1
      text       = "The API function crashed."
    }
    "lambda-throttles" = {
      namespace  = "AWS/Lambda"
      metric     = "Throttles"
      dimensions = { FunctionName = aws_lambda_function.api.function_name }
      statistic  = "Sum"
      threshold  = 1
      text       = "Requests were turned away: too many at once for the account's Lambda limit."
    }
    "cloudfront-5xx" = {
      namespace  = "AWS/CloudFront"
      metric     = "5xxErrorRate"
      dimensions = { DistributionId = aws_cloudfront_distribution.main.id, Region = "Global" }
      statistic  = "Average"
      threshold  = 5
      text       = "More than 5% of visitors got errors."
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "main" {
  for_each            = local.alarms
  alarm_name          = "${local.name}-${each.key}"
  alarm_description   = each.value.text
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  dimensions          = each.value.dimensions
  statistic           = each.value.statistic
  period              = 300
  evaluation_periods  = 1
  threshold           = each.value.threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

locals {
  fn = aws_lambda_function.api.function_name
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "API requests and errors"
          region = "us-east-1"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", local.fn],
            [".", "Errors", ".", "."],
            [".", "Throttles", ".", "."],
            ["SampCup", "ServerErrors"],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "API speed (ms) and concurrency"
          region = "us-east-1"
          period = 60
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", local.fn, { stat = "p95" }],
            [".", "ConcurrentExecutions", ".", ".", { stat = "Maximum", yAxis = "right" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "Visitors (CloudFront)"
          region = "us-east-1"
          period = 60
          metrics = [
            ["AWS/CloudFront", "Requests", "DistributionId", aws_cloudfront_distribution.main.id, "Region", "Global", { stat = "Sum" }],
            [".", "5xxErrorRate", ".", ".", ".", ".", { stat = "Average", yAxis = "right" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "Database reads and writes"
          region = "us-east-1"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.main.name],
            [".", "ConsumedWriteCapacityUnits", ".", "."],
          ]
        }
      },
      {
        type = "log", x = 0, y = 12, width = 24, height = 8
        properties = {
          title  = "Latest API errors"
          region = "us-east-1"
          view   = "table"
          query  = "SOURCE '${data.aws_cloudwatch_log_group.api.name}' | fields @timestamp, method, path, status, ms, @message | filter status >= 500 or @message like /Traceback|ERROR/ | sort @timestamp desc | limit 50"
        }
      },
    ]
  })
}
