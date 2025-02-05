#!/bin/bash
# make common python3 layer for all lambda functions
mkdir -p layer/python3_layer_content/python
cp -r layer/create_layer_virtualenv/lib layer/python3_layer_content/python/
(cd layer/python3_layer_content && zip -r ../python3_layer_content.zip python)

py_exclude=("*.pyc" "*__pycache__*" "*.pyo" "*.pyd")

# make mpic_coordinator lambda layer for mpic coordinator lambda function
mkdir -p layer/mpic_coordinator_layer_content/python
cp -r resources layer/mpic_coordinator_layer_content/python/resources  # TODO consider a more elegant approach
# Zip the mpic_coordinator lambda layer
(cd layer/mpic_coordinator_layer_content && zip -r ../mpic_coordinator_layer_content.zip python -x "${py_exclude[@]}")

# clean up, mostly for the IDE which could otherwise detect duplicate code
rm -r layer/python3_layer_content
rm -r layer/mpic_coordinator_layer_content
