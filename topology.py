"""Create five hosts, three switches, and two simple experiment commands."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
import config as C

BASE = Path(__file__).resolve().parent


class Lab:
    def __init__(self, net):
        self.net, self.processes = net, {}
        self.folder = BASE / 'results' / time.strftime('demo_%Y%m%d-%H%M%S')
        self.folder.mkdir()

    def stop(self, name):
        proc = self.processes.pop(name, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def start(self, name, host, command, path):
        self.stop(name)
        with open(path, 'w') as log:
            self.processes[name] = self.net.get(host).popen(command, stdout=log,
                stderr=subprocess.STDOUT, cwd=str(BASE))
        return self.processes[name]

    def flood(self, rate):
        if not 0 < rate <= 10:
            raise ValueError('Use flood 3, flood 6 or flood 9 (Mbps)')
        self.stop('flood-client')
        self.start('flood-server', 'h4', ['iperf', '-s', '-u', '-p', '5001', '-i', '1'], self.folder/'flood_receiver.txt')
        time.sleep(1)
        self.start('flood-client', 'h3', ['iperf', '-c', '10.0.0.4', '-u', '-b', f'{rate}M', '-t', '20', '-p', '5001'], self.folder/'flood_sender.txt')
        print(time.strftime('%H:%M:%S'), 'Traffic started for 20 seconds:', rate, 'Mbps')

    def compare(self, mode):
        state = C.read('network.json')
        if mode not in ('OFF', 'ON') or state.get('mitigation') != (mode == 'ON') or time.time()-state.get('updated', 0) > C.TIMEOUT:
            raise ValueError('Use compare OFF/ON with a fresh controller in that mode')
        if any(h.get('blocked') for h in state.get('hosts', {}).values()):
            raise ValueError('Wait for release or restart the lab before comparing')
        for name in ('flood-client', 'flood-server'):
            self.stop(name)
        folder = BASE/'results'/time.strftime(mode+'_%Y%m%d-%H%M%S')
        folder.mkdir()
        try:
            self.start('receiver', 'h4', ['iperf','-s','-u','-p','5002','-i','1'], folder/'victim.txt')
            self.start('attack-server', 'h3', ['iperf','-s','-u','-p','5001','-i','1'], folder/'attack_receiver.txt')
            time.sleep(1)
            self.start('victim', 'h1', ['iperf','-c','10.0.0.4','-u','-b','4M','-t','40','-p','5002'], folder/'victim_sender.txt')
            started = time.monotonic()
            time.sleep(10)
            attack_at = time.monotonic()-started
            self.start('attacker', 'h2', ['iperf','-c','10.0.0.3','-u','-b','10M','-t','20','-p','5001'], folder/'attack_sender.txt')
            time.sleep(34)
            (folder/'timing.txt').write_text(f'Attack launched {attack_at:.3f} seconds after victim launch; duration 20 seconds.\n')
        finally:
            for name in ('receiver', 'attack-server', 'victim', 'attacker'):
                self.stop(name)
            self.evidence(folder)
        print('Saved:', folder)

    def evidence(self, folder):
        for name in ('telemetry.json', 'network.json'):
            if (C.STATE/name).exists():
                shutil.copyfile(C.STATE/name, folder/name)
        if 'SUDO_UID' in os.environ:
            for path in [folder, *folder.iterdir()]:
                os.chown(path, int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))


class Commands(CLI):
    def do_flood(self, line):
        "flood 3|6|9: h3 sends to h4 for 20 seconds"
        try:
            self.mn.lab.flood(float(line))
        except ValueError as exc:
            print(exc)

    def do_compare(self, line):
        "compare OFF|ON: run a 44-second throughput comparison"
        try:
            self.mn.lab.compare(line.strip().upper())
        except ValueError as exc:
            print(exc)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run: sudo python3 topology.py')
    try:
        socket.create_connection(('127.0.0.1', 6653), timeout=2).close()
    except OSError:
        raise SystemExit('Start bash controller.sh on first')
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoStaticArp=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    switches = {i: net.addSwitch(f's{i}', dpid=f'{i:016x}', protocols='OpenFlow13', failMode='secure') for i in (1, 2, 3)}
    hosts = {i: net.addHost(f'h{i}', ip=f'10.0.0.{i}/24', mac=f'00:00:00:00:00:{i:02x}') for i in range(1, 6)}
    net.addLink(hosts[5], switches[1], port1=0, port2=1, bw=C.CAPACITY)
    net.addLink(switches[1], switches[2], port1=2, port2=3, bw=C.CAPACITY)
    net.addLink(switches[1], switches[3], port1=3, port2=3, bw=C.CAPACITY)
    for name, (switch, port) in C.HOSTS.items():
        net.addLink(hosts[int(name[1:])], switches[switch], port1=0, port2=port, bw=C.CAPACITY)
    lab = net.lab = Lab(net)
    try:
        net.start()
        if not net.waitConnected(timeout=20):
            raise RuntimeError('Switch connection failed')
        time.sleep(2)
        if net.pingAll():
            raise RuntimeError('Connectivity failed; inspect controller output')
        server = lab.start('collector', 'h5', [sys.executable, '-u', 'collector.py'], lab.folder/'collector.log')
        time.sleep(1)
        if server.poll() is not None:
            raise RuntimeError('Collector stopped; see its log in results/')
        for host in C.HOSTS:
            lab.start(host, host, [sys.executable, '-u', 'agent.py', host], lab.folder/(host+'.log'))
        print('Ready: flood 3 | flood 6 | flood 9 | compare OFF | compare ON')
        Commands(net)
    finally:
        for name in list(lab.processes):
            lab.stop(name)
        lab.evidence(lab.folder)
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
