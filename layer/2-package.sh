#!/bin/bash
# make common python3.11 layer for all lambda functions
mkdir -p python311_layer_content/python
cd python311_layer_content
cp -r ../create_layer_virtualenv/lib python/
zip -r ../python311_layer_content.zip python
cd ..

# make mpic_coordinator lambda layer for mpic coordinator lambda function
mkdir -p mpic_coordinator_layer_content/python/aws_lambda_python
cp -r ../src/aws_lambda_python/mpic_coordinator mpic_coordinator_layer_content/python/aws_lambda_python/mpic_coordinator
cd mpic_coordinator_layer_content
py_exclude=('*.pyc' '*__pycache__*')
zip -r ../mpic_coordinator_layer_content.zip python -x "${py_exclude[@]}" # Zip the mpic_coordinator lambda layer

