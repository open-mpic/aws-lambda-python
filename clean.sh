#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

FUNCTIONS_DIR='src/aws_lambda_python'

rm open-tofu/*.generated.tf

rm -r python/lib

rm -r layer/create_layer

rm layer/layer_content.zip

rm "${FUNCTIONS_DIR}"/lambda_validator/lambda_validator.zip

rm "${FUNCTIONS_DIR}"/lambda_mpic_coordinator/lambda_mpic_coordinator.zip

rm "${FUNCTIONS_DIR}"/lambda_caa_resolver/lambda_caa_resolver.zip