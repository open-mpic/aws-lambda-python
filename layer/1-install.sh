#!/bin/bash
python3.11 -m venv --clear create_layer_virtualenv
source create_layer_virtualenv/bin/activate
# need to explicitly set target directory to install dependencies when explicitly specifying platform
pip install -r requirements.txt --platform manylinux2014_aarch64 --only-binary=:all: --target "$VIRTUAL_ENV/lib/python3.11/site-packages"
