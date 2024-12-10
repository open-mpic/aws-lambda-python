#!/bin/bash
# make common python3.11 layer for all lambda functions
mkdir -p python311_layer_content/python
cd python311_layer_content
cp -r ../create_layer_virtualenv/lib python/
zip -r ../python311_layer_content.zip python
cd .. # should be at layer directory

py_exclude=('*.pyc' '*__pycache__*')

# make mpic_coordinator lambda layer for mpic coordinator lambda function
mkdir -p mpic_coordinator_layer_content/python
cp -r ../resources mpic_coordinator_layer_content/python/resources  # TODO consider a more elegant approach
cd mpic_coordinator_layer_content
zip -r ../mpic_coordinator_layer_content.zip python -x "${py_exclude[@]}" # Zip the mpic_coordinator lambda layer
rm -r python # clean up, mostly not to bother the IDE which will find this duplicate code!
cd .. # should be at layer directory


