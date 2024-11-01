#!/bin/bash
cd layer; ./1-install.sh; ./2-package.sh; cd ..; ./zip-all.sh; cd open-tofu; tofu apply -auto-approve; cd ..
