

resource "aws_api_gateway_resource" "validation" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  parent_id = aws_api_gateway_rest_api.open_mpic_api.root_resource_id

  path_part = "validation"

}


resource "aws_api_gateway_method" "validation" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validation.id

  http_method = "POST"

  authorization = "NONE"

}



resource "aws_api_gateway_integration" "validation_integration" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validation.id

  http_method = aws_api_gateway_method.validation.http_method

  integration_http_method = "POST"

  type = "AWS_PROXY"

  uri = aws_lambda_function.lambda_controller.invoke_arn



}



resource "aws_api_gateway_method_response" "validation" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validation.id

  http_method = aws_api_gateway_method.validation.http_method

  status_code = "200"

}



resource "aws_api_gateway_integration_response" "validation" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validation.id

  http_method = aws_api_gateway_method.validation.http_method

  status_code = aws_api_gateway_method_response.validation.status_code

  depends_on = [

    aws_api_gateway_method.validation,

    aws_api_gateway_integration.validation_integration

  ]

}