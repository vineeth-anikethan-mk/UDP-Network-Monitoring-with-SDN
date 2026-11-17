#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ $EUID -eq 0 ]]; then
  echo 'Run as your normal user: bash setup.sh'
  exit 1
fi
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf python3-venv python3-tk python3-matplotlib
sudo systemctl enable --now openvswitch-switch
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m unittest -v test_project.py
