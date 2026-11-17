#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "${1:-on}" in
  on) export MITIGATION=1 ;;
  off) export MITIGATION=0 ;;
  *) echo 'Use: bash controller.sh on|off'; exit 1 ;;
esac
if [[ ! -x .venv/bin/python ]]; then
  echo 'Run bash setup.sh first'; exit 1
fi
# Refuse a second controller. Exit Mininet before restarting this script.
python3 - <<'PY'
import socket
with socket.socket() as sock:
    try:
        sock.bind(('127.0.0.1', 6653))
    except OSError:
        raise SystemExit('Port 6653 is busy. Stop the old controller first.')
PY
mkdir -p results /tmp/jackfruit_simple
sudo rm -f /tmp/jackfruit_simple/telemetry.json /tmp/jackfruit_simple/network.json
.venv/bin/python -u run_controller.py 2>&1 | tee "results/controller_$(date +%Y%m%d-%H%M%S)_${1:-on}.log"
