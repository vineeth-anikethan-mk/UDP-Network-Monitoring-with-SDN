"""One place for network settings and shared JSON files."""
import json
import os
from pathlib import Path

STATE = Path('/tmp/jackfruit_simple')
SERVER = '10.0.0.5'
UDP_PORT = 9999
CAPACITY = 10                 # Mbps per link
WARNING = 5                  # Mbps
CRITICAL = 7                 # Mbps
POLL = 2                     # seconds
TIMEOUT = 5                  # telemetry/statistics freshness
HOLD = 15                    # minimum quarantine seconds
HOSTS = {'h1': (2, 1), 'h2': (2, 2), 'h3': (3, 1), 'h4': (3, 2)}


def save(name, data):
    """Replace the entire file so readers cannot see half-written JSON."""
    STATE.mkdir(exist_ok=True)
    temp = STATE / (name + '.tmp')
    temp.write_text(json.dumps(data))
    temp.chmod(0o644)
    os.replace(temp, STATE / name)


def read(name):
    try:
        return json.loads((STATE / name).read_text())
    except (OSError, ValueError):
        return {}
