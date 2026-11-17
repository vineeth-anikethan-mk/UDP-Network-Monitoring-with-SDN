"""Shared settings and helpers for the Network Monitoring and Alert System."""
import json
import os
from datetime import datetime

# ---- paths (all programs read/write here) ----
STATE_DIR = "/tmp/jackfruit"
STATE_FILE = STATE_DIR + "/state.json"            # written by collector (application view)
NET_STATE_FILE = STATE_DIR + "/net_state.json"    # written by controller (network view)
COLLECTOR_ALERT_LOG = STATE_DIR + "/alerts_collector.log"
CONTROLLER_ALERT_LOG = STATE_DIR + "/alerts_controller.log"

# ---- network ----
SERVER_IP = "10.0.0.5"        # h5 = monitoring server
TELEMETRY_PORT = 9999         # UDP port of the monitoring server
OFP_PORT = 6653               # OpenFlow port of the controller
LINK_BW_MBPS = 10             # every Mininet link is 10 Mbps

# ---- telemetry agent / collector ----
SEND_INTERVAL = 1.0           # seconds between telemetry datagrams
DOWN_AFTER_SEC = 5            # no telemetry for this long -> node DOWN
TX_WARN_MBPS = 5.0            # host-reported send rate thresholds
TX_CRIT_MBPS = 7.0
LOSS_WINDOW_SEC = 10          # window for telemetry loss %
LOSS_WARN_PCT = 20.0
DELAY_WARN_MS = 300.0

# ---- controller ----
POLL_SEC = 2                  # statistics polling period
UTIL_WARN_PCT = 50.0          # link/port utilisation thresholds (% of LINK_BW_MBPS)
UTIL_CRIT_PCT = 70.0
HOT_POLLS = 2                 # consecutive CRITICAL polls before quarantine
QUARANTINE_SEC = 15           # minimum quarantine time


def ensure_dir():
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        os.chmod(STATE_DIR, 0o777)
    except OSError:
        pass


def write_json_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    try:
        os.chmod(tmp, 0o644)
    except OSError:
        pass
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def log_line(path, text):
    line = "%s %s" % (datetime.now().strftime("%H:%M:%S.%f")[:-3], text)
    print(line, flush=True)
    try:
        with open(path, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass
    return line
