"""Each host sends its measured TX/RX rates to h5 once per second."""
import json
import socket
import sys
import time
import config as C


def counters():
    for line in open('/proc/net/dev'):
        if ':' in line:
            interface, values = line.split(':', 1)
            if interface.strip() != 'lo':
                values = values.split()
                return int(values[8]), int(values[0])  # TX bytes, RX bytes
    raise RuntimeError('No host network interface found')


def main():
    node = sys.argv[1]
    if node not in C.HOSTS:
        raise SystemExit('Use: python3 agent.py h1 (or h2/h3/h4)')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    old_tx, old_rx = counters()
    previous = time.monotonic()
    while True:
        time.sleep(1)
        tx, rx = counters()
        now = time.monotonic()
        elapsed = now - previous
        message = {'node': node, 'tx': max(0, tx-old_tx)*8/elapsed/1e6,
                   'rx': max(0, rx-old_rx)*8/elapsed/1e6}
        old_tx, old_rx, previous = tx, rx, now
        try:
            sock.sendto(json.dumps(message).encode(), (C.SERVER, C.UDP_PORT))
        except OSError:
            pass  # A temporary link failure must not terminate the agent.


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
