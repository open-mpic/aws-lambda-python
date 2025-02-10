#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

FUNCTIONS_DIR="src/aws_lambda_mpic"

$(rm open-tofu/*.generated.tf 2> /dev/null) || true

$(rm layer/*.zip 2> /dev/null) || true
#$(rm -r layer/create_layer_virtualenv 2> /dev/null) || true

$(rm "${FUNCTIONS_DIR}"/mpic_coordinator_lambda/mpic_coordinator_lambda.zip 2> /dev/null) || true
$(rm "${FUNCTIONS_DIR}"/mpic_caa_checker_lambda/mpic_caa_checker_lambda.zip 2> /dev/null) || true
$(rm "${FUNCTIONS_DIR}"/mpic_dcv_checker_lambda/mpic_dcv_checker_lambda.zip 2> /dev/null) || true
