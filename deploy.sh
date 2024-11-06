#!/bin/bash
./clean.sh; cd layer; ./1-install.sh; ./2-package.sh; cd ..; hatch run ./configure.py; ./zip-all.sh; cd open-tofu; tofu apply -auto-approve; cd ..
