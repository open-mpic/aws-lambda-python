#!/bin/bash


SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

FUNCTIONS_DIR='src/aws_lambda_python'

cd "${FUNCTIONS_DIR}"/lambda_validator # Change to the directory of the lambda function
zip lambda_validator.zip lambda_function.py
cd $SCRIPT_DIR

cd "${FUNCTIONS_DIR}"/lambda_mpic_coordinator
zip -r lambda_mpic_coordinator.zip .
cd $SCRIPT_DIR

cd "${FUNCTIONS_DIR}"/lambda_caa_resolver
zip lambda_caa_resolver.zip lambda_function.py
cd $SCRIPT_DIR