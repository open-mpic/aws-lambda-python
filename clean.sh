#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

rm open-tofu/*.generated.tf

rm -r python/lib

rm -r layer/create_layer

rm layer/layer_content.zip

rm src/aws_lambda_python/lambda_validator/lambda_validator.zip

rm src/aws_lambda_python/lambda_controller/lambda_controller.zip

rm src/aws_lambda_python/lambda_caa_resolver/lambda_caa_resolver.zip