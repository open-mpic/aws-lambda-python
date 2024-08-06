#!/bin/bash
python3.11 -m venv --clear create_layer_virtualenv
source create_layer_virtualenv/bin/activate
pip install -r requirements.txt
