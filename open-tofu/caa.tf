

resource "aws_api_gateway_resource" "caa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  parent_id = aws_api_gateway_rest_api.open_mpic_api.root_resource_id

  path_part = "caa-lookup"

}


resource "aws_api_gateway_method" "caa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.caa.id

  http_method = "POST"

  authorization = "NONE"

  api_key_required = true

}



resource "aws_api_gateway_integration" "caa_integration" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.caa.id

  http_method = aws_api_gateway_method.caa.http_method

  integration_http_method = "POST"

  type = "AWS_PROXY"

  uri = aws_lambda_function.lambda_controller.invoke_arn



}



resource "aws_api_gateway_method_response" "caa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.caa.id

  http_method = aws_api_gateway_method.caa.http_method

  status_code = "200"

}



resource "aws_api_gateway_integration_response" "caa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.caa.id

  http_method = aws_api_gateway_method.caa.http_method

  status_code = aws_api_gateway_method_response.caa.status_code

  depends_on = [

    aws_api_gateway_method.caa,

    aws_api_gateway_integration.caa_integration

  ]

}