#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

FUNCTIONS_DIR="src/aws_lambda_mpic"

rm open-tofu/*.generated.tf

rm layer/*.zip
rm -r layer/create_layer_virtualenv

rm "${FUNCTIONS_DIR}"/mpic_coordinator_lambda/mpic_coordinator_lambda.zip
rm "${FUNCTIONS_DIR}"/mpic_caa_checker_lambda/mpic_caa_checker_lambda.zip
rm "${FUNCTIONS_DIR}"/mpic_dcv_checker_lambda/mpic_dcv_checker_lambda.zip
