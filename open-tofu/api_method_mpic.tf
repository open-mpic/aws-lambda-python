resource "aws_api_gateway_resource" "mpic" {
  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id
  parent_id = aws_api_gateway_rest_api.open_mpic_api.root_resource_id
  path_part = "mpic"
}

resource "aws_api_gateway_method" "mpic" {
  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id
  resource_id = aws_api_gateway_resource.mpic.id
  http_method = "POST"
  authorization = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "mpic_integration" {
  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id
  resource_id = aws_api_gateway_resource.mpic.id
  http_method = aws_api_gateway_method.mpic.http_method
  integration_http_method = "POST"
  type = "AWS_PROXY"
  uri = aws_lambda_function.mpic_coordinator_lambda.invoke_arn
}

resource "aws_api_gateway_method_response" "mpic" {
  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id
  resource_id = aws_api_gateway_resource.mpic.id
  http_method = aws_api_gateway_method.mpic.http_method
  status_code = "200"
}

resource "aws_api_gateway_integration_response" "mpic" {
  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id
  resource_id = aws_api_gateway_resource.mpic.id
  http_method = aws_api_gateway_method.mpic.http_method
  status_code = aws_api_gateway_method_response.mpic.status_code
  depends_on = [
    aws_api_gateway_method.mpic,
    aws_api_gateway_integration.mpic_integration
  ]
}