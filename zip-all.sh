#!/bin/bash


SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

cd lambda_validator
zip lambda_validator.zip lambda_function.py
cd ..

cd lambda_controller
zip lambda_controller.zip lambda_function.py
cd ..

cd lambda_caa_resolver
zip lambda_caa_resolver.zip lambda_function.py
cd ..