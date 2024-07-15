

resource "aws_api_gateway_resource" "validationwithcaa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  parent_id = aws_api_gateway_rest_api.open_mpic_api.root_resource_id

  path_part = "validation-with-caa-check"

}


resource "aws_api_gateway_method" "validationwithcaa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validationwithcaa.id

  http_method = "POST"

  authorization = "NONE"

  api_key_required = true

}



resource "aws_api_gateway_integration" "validationwithcaa_integration" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validationwithcaa.id

  http_method = aws_api_gateway_method.validationwithcaa.http_method

  integration_http_method = "POST"

  type = "AWS_PROXY"

  uri = aws_lambda_function.lambda_controller.invoke_arn



}



resource "aws_api_gateway_method_response" "validationwithcaa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validationwithcaa.id

  http_method = aws_api_gateway_method.validationwithcaa.http_method

  status_code = "200"

}



resource "aws_api_gateway_integration_response" "validationwithcaa" {

  rest_api_id = aws_api_gateway_rest_api.open_mpic_api.id

  resource_id = aws_api_gateway_resource.validationwithcaa.id

  http_method = aws_api_gateway_method.validationwithcaa.http_method

  status_code = aws_api_gateway_method_response.validationwithcaa.status_code

  depends_on = [

    aws_api_gateway_method.validationwithcaa,

    aws_api_gateway_integration.validationwithcaa_integration

  ]

}