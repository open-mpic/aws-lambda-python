#!/bin/bash
./clean.sh; hatch env prune; hatch run lambda-layer:install; cd layer; ./package.sh; cd ..; hatch run ./configure.py; ./zip-all.sh; cd open-tofu; tofu apply -var="dnssec_enabled=false" -auto-approve; cd ..
