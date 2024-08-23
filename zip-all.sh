#!/bin/bash


SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

FUNCTIONS_DIR="src/aws_lambda_python"

cd "${FUNCTIONS_DIR}"/lambda_validator # Change to the directory of the lambda function
zip lambda_validator.zip lambda_function.py
cd $SCRIPT_DIR

cd "${FUNCTIONS_DIR}"/mpic_coordinator_lambda
zip -r mpic_coordinator_lambda.zip mpic_coordinator_lambda_function.py
cd $SCRIPT_DIR

cd "${FUNCTIONS_DIR}"/mpic_caa_checker_lambda
zip mpic_caa_checker_lambda.zip mpic_caa_checker_lambda_function.py
cd $SCRIPT_DIR