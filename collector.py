"""h5 receives UDP reports; a second thread publishes current host status."""
import json
import math
import socket
import threading
import time
import config as C


class Collector:
    def __init__(self):
        self.nodes = {}
        self.lock = threading.Lock()

    def accept(self, data, address):
        try:
            report = json.loads(data)
            node = report['node']
            tx, rx = float(report['tx']), float(report['rx'])
            if node not in C.HOSTS or address[0] != '10.0.0.' + node[1:]:
                return False
            if not all(math.isfinite(v) and v >= 0 for v in (tx, rx)):
                return False
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return False
        with self.lock:
            self.nodes[node] = {'tx': tx, 'rx': rx, 'seen': time.time()}
        return True

    def snapshot(self):
        now = time.time()
        with self.lock:
            nodes = {}
            for host in C.HOSTS:
                report = self.nodes.get(host, {})
                up = now - report.get('seen', 0) < C.TIMEOUT
                nodes[host] = dict(report, status='UP' if up else 'DOWN')
        return {'updated': now, 'nodes': nodes}


def main():
    collector = Collector()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', C.UDP_PORT))

    def receive():
        while True:
            data, address = sock.recvfrom(4096)
            collector.accept(data, address)

    threading.Thread(target=receive, daemon=True).start()
    previous = {}
    while True:
        state = collector.snapshot()
        for host, report in state['nodes'].items():
            status = report['status']
            if status != previous.get(host):
                print(time.strftime('%H:%M:%S'), host, status, flush=True)
                previous[host] = status
        C.save('telemetry.json', state)
        time.sleep(1)


if __name__ == '__main__':
    main()
