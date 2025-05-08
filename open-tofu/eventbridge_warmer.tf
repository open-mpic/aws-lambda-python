resource "aws_scheduler_schedule" "open_mpic_warmer_schedule" {
  for_each = {
    for k, v in {
      # TODO instead of using valid MPIC requests, evaluate to modify the coordinator Lambda to receive an especial parameter to trigger the warmup of all the perspectives. That would simplify things by requiring a single warmer, instead of two, as now.
      caa = {
        check_type          = "caa"
        domain_or_ip_target = "invalid"
        orchestration_parameters = {
          perspective_count = length(keys(local.perspectives))
        }
      }
      dcv = {
        check_type          = "dcv"
        domain_or_ip_target = "invalid"
        dcv_check_parameters = {
          validation_method = "dns-change"
          dns_record_type   = "TXT"
          challenge_value   = "dummy"
        }
        orchestration_parameters = {
          perspective_count = length(keys(local.perspectives))
        }
      }
    } : k => v if var.eventbridge_warmer_enabled
  }
  name       = "open-mpic-${each.key}-warmer-schedule-${local.deployment_id}"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "rate(5 minutes)"

  target {
    arn      = aws_lambda_function.mpic_coordinator_lambda.arn
    role_arn = aws_iam_role.open_mpic_warmer_role[0].arn
    input = jsonencode({
      resource   = "/dummy",
      path       = "/dummy",
      httpMethod = "POST",
      headers = {},
      multiValueHeaders = {},
      requestContext = {
        accountId = "dummy",
        apiId     = "dummy",
        stage     = "dummy",
        protocol  = "dummy",
        identity = {
          sourceIp = "0.0.0.0"
        },
        requestId        = "dummy",
        requestTime      = "dummy",
        requestTimeEpoch = 0,
        resourcePath     = "dummy",
        httpMethod       = "POST",
        path             = "dummy"
      },
      body = jsonencode(each.value)
    })
  }
}

resource "aws_iam_role" "open_mpic_warmer_role" {
  count = var.eventbridge_warmer_enabled ? 1 : 0
  name  = "open-mpic-warmer-role-${local.deployment_id}"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "scheduler.amazonaws.com"
      },
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy" "open_mpic_warmer_role_policy" {
  count  = var.eventbridge_warmer_enabled ? 1 : 0
  name   = "open-mpic-warmer-role-policy-${local.deployment_id}"
  role   = aws_iam_role.open_mpic_warmer_role[0].name
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "lambda:InvokeFunction",
      "Resource": [
        "${aws_lambda_function.mpic_coordinator_lambda.arn}"
      ],
      "Effect": "Allow"
    }
  ]
}
EOF
}
