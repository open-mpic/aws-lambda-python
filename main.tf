provider "aws" {
  region                  = "us-east-2"
  profile                 = "default"
}

# Python openmpic layer.
resource "aws_lambda_layer_version" "python311-open-mpic-layer" {
    filename            = "layer/layer_content.zip"
    layer_name          = "python_311_open_mpic_layer"
    source_code_hash    = "${filebase64sha256("layer/layer_content.zip")}"
    compatible_runtimes = ["python3.11"]
}

resource "aws_iam_role" "open_mpic_lambda_role" {
  name = "open-mpic-lambda-role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

data "aws_iam_policy" "AWSLambdaBasicExecutionRole" {
  arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "basic-execution-policy-attach" {
  role       = "${aws_iam_role.open_mpic_lambda_role.name}"
  policy_arn = "${data.aws_iam_policy.AWSLambdaBasicExecutionRole.arn}"
}


resource "aws_iam_role_policy_attachment" "invoke-lambda-policy-attach" {
  role       = "${aws_iam_role.open_mpic_lambda_role.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
}



resource "aws_lambda_function" "lambda_validator" {
    filename      = "lambda_validator/lambda_validator.zip"
    function_name = "open_mpic_lambda_validator"
    role          = aws_iam_role.open_mpic_lambda_role.arn
    handler       = "lambda_function.lambda_handler"
    source_code_hash = filebase64sha256("lambda_validator/lambda_validator.zip")
    runtime = "python3.11"
    layers = [aws_lambda_layer_version.python311-open-mpic-layer.arn]
}

resource "aws_lambda_function" "lambda_caa_resolver" {
    filename      = "lambda_caa_resolver/lambda_caa_resolver.zip"
    function_name = "open_mpic_lambda_caa_resolver"
    role          = aws_iam_role.open_mpic_lambda_role.arn
    handler       = "lambda_function.lambda_handler"
    source_code_hash = filebase64sha256("lambda_caa_resolver/lambda_caa_resolver.zip")
    runtime = "python3.11"
    layers = [aws_lambda_layer_version.python311-open-mpic-layer.arn]
}

resource "aws_lambda_function" "lambda_controller" {
    filename      = "lambda_controller/lambda_controller.zip"
    function_name = "open_mpic_lambda_controller"
    role          = aws_iam_role.open_mpic_lambda_role.arn
    handler       = "lambda_function.lambda_handler"
    source_code_hash = filebase64sha256("lambda_controller/lambda_controller.zip")
    runtime = "python3.11"
    timeout = 60
    layers = [aws_lambda_layer_version.python311-open-mpic-layer.arn]
    environment {
      variables = {
        validator_arn = aws_lambda_function.lambda_validator.arn
        caa_arn = aws_lambda_function.lambda_caa_resolver.arn
      }
    }

}


resource "aws_api_gateway_rest_api" "open_mpic_api" {
  name = "open-mpic-api"
  description = "Open MPIC API Gateway"
  endpoint_configuration {
    types = ["EDGE"]
  }
}




resource "aws_api_gateway_deployment" "deployment" {

  depends_on = [

    aws_api_gateway_integration.validation_integration,
    aws_api_gateway_integration.caa_integration,
    aws_api_gateway_integration.validationwithcaa_integration,
    
  ]



  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  stage_name = "dev"

}


resource "aws_lambda_permission" "lambda_permission_api" {
  statement_id  = "AllowOpenMPICAPIInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_controller.function_name
  principal     = "apigateway.amazonaws.com"

  # The /* part allows invocation from any stage, method and resource path
  # within API Gateway.
  source_arn = "${aws_api_gateway_rest_api.open_mpic_api.execution_arn}/*"
}
