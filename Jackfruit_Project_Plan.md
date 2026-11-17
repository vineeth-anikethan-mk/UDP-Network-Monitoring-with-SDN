# Jackfruit Mini Project: Network Monitoring and Alert System (Topic 6, UDP)

Group of 3 (Person A, Person B, Person C). Everything below is tested copy-paste code. Do the steps **in order**. Create files with the **exact names** given.

## Order of work at a glance

| Step | What | Who |
|---|---|---|
| Read | Section 1 (what the project is) and Section 2 (shortforms) | everyone |
| Step 1 | Set up the Virtual Machine (VM) | everyone |
| Step 2 | Install Mininet, Ryu and tools | everyone |
| Step 3 | Create the shared GitHub repo and clone it | C creates, everyone clones |
| Step 4 | Build the UDP socket side | A |
| Step 5 | Build the SDN controller | B |
| Step 6 | Build the Mininet topology and plot script | C |
| Step 7 | Put it all together and run the smoke test | everyone (C leads) |
| Step 8 | Run the experiments and record results | A, B, C (one each) |
| Step 9 | Prepare the submission and the demo | C leads, everyone writes their part |
| Step 10 | Prepare for the viva | everyone |

Tick a step only when its "Done when" check passes.

---

## 1. What the project actually is

**In one line:** we build a small virtual network where every computer reports its own health over **UDP**, a central server collects those reports, and an **SDN controller** compares what the computers *say* about themselves with what the network switches actually *see*. If both agree that something is abnormal, the system raises an alert and the controller automatically blocks that computer. Then we measure how much better this is than a network that only watches and never blocks.

**A real-life picture:** think of a building. Each room (host) has a sensor that sends a "status report" every second to a control room (monitoring server). The corridors (switches) also have counters that count how many people pass. A security manager (controller) checks both: if a room's sensor says "I'm sending a huge amount of traffic" **and** the corridor counter agrees, the manager locks that room's door (blocks it), but leaves the intercom line (telemetry) open so the room is still monitored.

### The four parts

| Part | Runs on | What it does |
|---|---|---|
| **Telemetry agents** (`agent.py`) | h1, h2, h3, h4 | Every 1 second, send one UDP datagram (a small JSON message) to the server: node name, sequence number, timestamp, send/receive rate |
| **Monitoring server** (`collector.py`) | h5 (10.0.0.5, UDP port 9999) | Receives all reports, tracks each node, detects: node DOWN, lost reports, delay, high send rate. Saves its view in `state.json` |
| **SDN controller** (`controller.py`, built with Ryu, speaks OpenFlow 1.3) | your VM | Acts as the "brain" of the switches. Every 2 seconds it asks each switch for statistics, calculates utilisation, reads `state.json`, raises alerts and blocks a confirmed abnormal host |
| **Mininet topology** (`topo.py`) | your VM | Creates the virtual network: 3 switches, 5 hosts, 10 Mbps links; starts the server and agents |

```
            h5 (monitoring server 10.0.0.5, UDP 9999)
             |
   c0 ----- s1 ---------- s3 -- h3, h4
 (Ryu)       |
            s2 -- h1, h2          h1..h4 run telemetry agents
```
`c0` is the controller. Every switch (s1, s2, s3) connects to it.

### How it works, step by step
1. **Agents report.** Each agent reads its own interface counters, works out its send/receive rate and sends a UDP message to h5. Each message carries a number (`seq`) that increases by 1; if the server sees a jump, a message was lost.
2. **Server analyses.** `collector.py` marks a node DOWN if it hears nothing for 5 s, measures loss over the last 10 s and the delay, and notes the node's reported send rate. It writes everything to `/tmp/jackfruit/state.json` and prints alerts.
3. **Controller measures the network.** Every 2 s it requests port statistics and flow statistics from each switch. **Utilisation = bytes counted × 8 ÷ seconds ÷ link capacity (10 Mbps) × 100%.**
4. **Controller combines both views** (this is the link between the sockets and the SDN part: it reads `state.json`):
   - switch sees ≥ 70% from a host **and** the host's own agent reports ≥ 7 Mbps → **CRITICAL: confirmed abnormal sender**
   - switch sees ≥ 70% but the agent reports little or nothing → WARNING (mismatch or no telemetry)
   - ≥ 50% → WARNING
   - a link between switches ≥ 50% / ≥ 70% → congestion WARNING / CRITICAL
5. **Controller reacts.** A host that stays CRITICAL for 2 checks in a row is **quarantined**: the controller installs flow rules on its switch that drop everything from that host **except ARP and the telemetry port**. The host is released when its traffic falls below 50% (after at least 15 s).
6. **Failures are detected.** A broken link produces an OpenFlow Port-Status message to the controller; a dead host stops sending reports.
7. **Presentation.** `dashboard.py` shows everything live in a terminal; alerts are saved in log files.

### Why this satisfies the assignment
| Assignment expectation | Where |
|---|---|
| Implement UDP telemetry agents | `agent.py` |
| Develop a centralized monitoring server | `collector.py` |
| Collect SDN flow statistics | `controller.py` (port + flow statistics requests) |
| Calculate traffic utilization | `controller.py`, function `_evaluate` |
| Define abnormality thresholds | `jf_config.py` |
| Generate alerts | collector and controller logs |
| Monitor multiple network nodes | 4 agents, 3 switches |
| Present monitoring results | `dashboard.py`, logs, graph |
| Dynamic SDN functionality | monitoring + automatic quarantine and release |
| Challenging scenario | flood congestion, telemetry loss, link failure, node failure |
| Comparison with a baseline | `MITIGATION=0` (watch only) vs `MITIGATION=1` (watch and block) |

---

## 2. Shortforms used in this document

| Term | Meaning |
|---|---|
| **VM** | Virtual Machine: a computer simulated inside your computer (we use it to run Linux) |
| **OS** | Operating System (here Ubuntu Linux) |
| **NAT** | Network Address Translation: the VM shares your PC's internet connection |
| **CLI** | Command Line Interface: the `mininet>` prompt where you type commands |
| **SDN** | Software-Defined Networking: the decision-making ("control plane") of the network is moved out of the switches into one central program, the controller |
| **Controller** | the central program that tells switches what to do (ours is built with **Ryu**, a Python SDN framework) |
| **OpenFlow (OF)** | the protocol a controller uses to talk to switches. We use version **1.3** |
| **OVS** | Open vSwitch: the software switch Mininet uses |
| **Mininet** | a tool that creates a virtual network (hosts, switches, links) on one machine |
| **Host / h1…h5** | a virtual computer in Mininet. **s1…s3** = switches, **c0** = controller |
| **Flow / flow entry** | a rule in a switch: "if a packet matches X, do Y" (e.g., drop it) |
| **Match / action / priority** | the parts of a flow entry; the highest priority matching entry wins |
| **Table-miss** | the lowest-priority rule that sends unknown packets to the controller |
| **Packet-In / Packet-Out / Flow-Mod** | OpenFlow messages: switch→controller (unknown packet), controller→switch (send this packet), controller→switch (add/remove a rule) |
| **Port-Status** | OpenFlow message telling the controller that a port went up or down |
| **dpid** | datapath ID: the number identifying a switch (s1 = 1, s2 = 2, s3 = 3) |
| **UDP** | User Datagram Protocol: sends independent messages with no connection and no delivery guarantee |
| **TCP** | Transmission Control Protocol: reliable, connection-based (not used for telemetry here) |
| **Datagram** | one UDP message |
| **Socket** | the programming interface used to send/receive network data |
| **IP / MAC** | the logical address (10.0.0.1) and the hardware address (00:00:00:00:00:01) of a host |
| **ARP** | Address Resolution Protocol: how a host finds the MAC of an IP address |
| **ICMP / ping** | simple "are you there?" test messages |
| **iperf** | a tool that generates network traffic at a chosen rate so we can test |
| **Mbps** | megabits per second (link speed). **pps** = packets per second |
| **TX / RX** | transmit (sent) / receive (received) |
| **Utilisation (util)** | how much of a link's capacity is in use, in % |
| **WARN / CRIT** | alert levels: WARNING and CRITICAL |
| **JSON** | a text format for structured data, e.g. `{"node": "h1", "seq": 5}` |
| **seq** | sequence number of a telemetry message |
| **Quarantine** | blocking a host's traffic except ARP and telemetry |
| **Baseline** | the "before" system we compare against (watch-only, no blocking) |
| **veth / namespace** | how Mininet fakes hosts: each host is a separate network namespace connected by virtual cables (veth pairs) |
| **TCLink / HTB** | a Mininet link type that limits speed; HTB = Hierarchical Token Bucket, the Linux speed-limiting method behind it |
| **git / GitHub / repo / README** | version control tool / website hosting it / repository (project folder) / the project's description file |
| **D1 / D2** | the two deliverables in the evaluation (D1 = 15 marks, D2 = 25 marks) |
| **Viva** | the oral exam where each of you explains the project |

---

## Step 1: Set up the Virtual Machine (everyone)

Mininet needs Linux with administrator (`sudo`) rights. If you already run Ubuntu natively, skip to Step 2. Otherwise, each of you creates a VM (this matches the college "Mininet Installation Manual").

1. **Install VM software:** VirtualBox (virtualbox.org) or VMware Workstation Player / Fusion. Pick one.
2. **Download Ubuntu:** Ubuntu **22.04 LTS** Desktop ISO from ubuntu.com (20.04 also works). On Apple-silicon Macs use the ARM64 Ubuntu 22.04 image with UTM or VMware Fusion.
3. **Create the VM** with these settings:
   - Memory: **4 GB** (2 GB minimum)
   - CPU: **2** cores
   - Disk: **25 GB**
   - Network adapter: **NAT** (or Bridged)
4. **Install Ubuntu** from the ISO (normal install, "Erase disk" refers only to the virtual disk). Create a user; this user automatically has `sudo`.
5. **First boot:** open a terminal (Ctrl+Alt+T) and run:
```bash
sudo apt update
sudo apt upgrade -y
```
Reboot the VM afterwards.
6. **Optional but useful:** enable copy-paste between your PC and the VM (VirtualBox: *Devices → Shared Clipboard → Bidirectional*; install guest additions if asked). You will paste a lot of code.

**Done when:** the VM has internet. Check:
```bash
ping -c 3 google.com
lsb_release -a
```
`ping` should show replies (0% packet loss) and `lsb_release` should show Ubuntu 20.04 or 22.04.

---

## Step 2: Install Mininet, Ryu and tools (everyone)

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf git python3-matplotlib python3-ryu
```
What each one is: `mininet` (virtual network), `openvswitch-switch` (the virtual switch), `iperf` (traffic generator), `git` (version control), `python3-matplotlib` (graphs), `python3-ryu` (the controller framework).

**If `apt install` does not work:** use `apt-get` instead (same arguments), e.g. `sudo apt-get install -y mininet openvswitch-switch iperf git python3-matplotlib python3-ryu`.

**Alternative: install Mininet from source (optional, advanced; only if the apt method fails):**
```bash
sudo apt install git build-essential python3-pip -y
git clone https://github.com/mininet/mininet
cd mininet
sudo ./util/install.sh -a
cd ..
```
If you see Open vSwitch errors: `sudo apt install openvswitch-switch -y`.

**Check Ryu:**
```bash
ryu-manager --version
```
If `ryu-manager` is not found, run `sudo apt install -y ryu-bin` and check again.
Only if both fail, use this fallback (you must then start the controller from this venv, a private Python environment):
```bash
sudo apt install -y python3-venv
python3 -m venv ~/ryu-env && source ~/ryu-env/bin/activate
pip install -U pip wheel pbr "setuptools<66"
pip install "eventlet==0.30.2" "dnspython<2"
pip install ryu --no-build-isolation
```

**Check Mininet:**
```bash
sudo mn --test pingall
sudo mn -c
```
Expected: the test creates a default network (1 switch, 2 hosts) and prints `0% dropped`. `sudo mn -c` cleans up leftovers (do this whenever Mininet behaves strangely).

The college manual does the same test by hand: run `sudo mn` (a default network and the `mininet>` prompt appear), type `pingall` (expect `0% dropped`), then `exit`. You can also try `sudo mn --topo single,3` (1 switch, 3 hosts); use `nodes`, `net` and `dump` to look around.

### Mininet in 2 minutes (needed for the demo and the viva)
- Mininet creates virtual hosts (separate network namespaces), virtual Open vSwitch switches and virtual Ethernet (veth) links on one machine. Hosts run real programs, so the same `python3` and `iperf` you use normally run inside them.
- In this project you do **not** type a topology yourself: `sudo python3 topo.py` builds the 3 switches, 5 hosts and links, connects to the Ryu controller, starts the server and agents, and opens the `mininet>` prompt.
- Commands at the `mininet>` prompt:

| Command | Meaning |
|---|---|
| `nodes`, `net`, `dump` | list nodes, show connections, node details |
| `pingall` | connectivity test between all hosts |
| `h1 ping -c 3 10.0.0.2` | run a command **on a host** (host name first) |
| `sh <cmd>` | run a command on the VM itself (e.g. `sh ovs-ofctl -O OpenFlow13 dump-flows s2`) |
| `link s1 s3 down` / `up` | fail / restore a link |
| `agent h1 0.4` | our own command: restart h1's agent dropping 40% of its messages |
| `exit` | leave the CLI; then run `sudo mn -c` |

**Done when:** `ryu-manager --version` prints a version and the Mininet test printed `0% dropped`.

---

## Step 3: Shared GitHub repo (C creates, everyone clones)

**Person C (once):** on github.com create a repository named `jackfruit-sdn-monitor` (tick "Add a README file"), and add A and B as collaborators (*Settings → Collaborators*).

**Everyone, in the VM:**
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
cd ~
git clone <repo-url> jackfruit-sdn-monitor
cd jackfruit-sdn-monitor
mkdir -p results
```
GitHub asks for your username and a **personal access token** instead of a password (GitHub → *Settings → Developer settings → Personal access tokens*).

**How you share files from now on** (each person adds only their own files):
```bash
git add <your files>
git commit -m "Add <what you added>"
git pull --rebase
git push
```
Everyone else gets the new files with `git pull`. Every command in this document is run **inside `~/jackfruit-sdn-monitor`**. Keep the path without spaces.

**Done when:** all three of you can run `git pull` in the folder without errors.

---

## Step 4: Person A, the UDP socket side

**What you are building (plain words):** the part that *produces and receives the monitoring reports*. The agent runs on each host and sends a small report every second; the server receives reports from all agents at once, spots problems and publishes its findings; the dashboard shows them. `jf_config.py` holds all the numbers (ports, thresholds) in one place so nobody hardcodes them.

**Do first:** create `jf_config.py` and push it right away, because B and C need it.

1. `jf_config.py` (shared settings and helper functions):

```python
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
```

2. `agent.py`. How it works: reads the host's network counters from `/proc/net/dev`, computes TX/RX rate since the last report, builds a JSON message with an increasing `seq`, sends it with `sendto`. `--drop` skips sending on purpose to simulate loss. If the network is down, the send error is caught and it keeps running.

```python
#!/usr/bin/env python3
"""UDP telemetry agent - runs on every monitored host.
Sends one JSON datagram per interval to the monitoring server."""
import argparse
import json
import random
import socket
import time

import jf_config as C


def read_counters():
    """(iface, rx_bytes, rx_packets, tx_bytes, tx_packets) of first non-loopback interface."""
    with open("/proc/net/dev") as f:
        lines = f.readlines()[2:]
    for line in lines:
        name, data = line.split(":", 1)
        if name.strip() == "lo":
            continue
        v = data.split()
        return name.strip(), int(v[0]), int(v[1]), int(v[8]), int(v[9])
    return "none", 0, 0, 0, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--server", default=C.SERVER_IP)
    ap.add_argument("--port", type=int, default=C.TELEMETRY_PORT)
    ap.add_argument("--interval", type=float, default=C.SEND_INTERVAL)
    ap.add_argument("--drop", type=float, default=0.0,
                    help="probability (0-1) of NOT sending a datagram (simulates telemetry loss)")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _, rb0, rp0, tb0, tp0 = read_counters()
    last = time.time()
    seq = 0
    while True:
        time.sleep(args.interval)
        now = time.time()
        iface, rb, rp, tb, tp = read_counters()
        dt = max(now - last, 1e-6)
        seq += 1
        msg = {
            "node": args.name, "seq": seq, "ts": now, "iface": iface,
            "tx_mbps": round((tb - tb0) * 8 / dt / 1e6, 3),
            "rx_mbps": round((rb - rb0) * 8 / dt / 1e6, 3),
            "tx_pps": round((tp - tp0) / dt, 1),
            "rx_pps": round((rp - rp0) / dt, 1),
        }
        last, rb0, rp0, tb0, tp0 = now, rb, rp, tb, tp
        if random.random() < args.drop:
            continue                       # seq still advanced -> collector sees a gap
        try:
            sock.sendto(json.dumps(msg).encode(), (args.server, args.port))
        except OSError:
            pass                           # network down: keep running


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
```

3. `collector.py`. How it works: a **receiver thread** waits on `recvfrom`, parses each datagram (bad ones are ignored) and updates the node's record under a lock; the **main loop** runs every second, decides status/alerts (DOWN after 5 s of silence, loss over a 10 s window, delay, high TX), prints/logs alerts only when they appear/change/clear, and writes `state.json` safely (write to a temp file, then replace).

```python
#!/usr/bin/env python3
"""Centralized UDP monitoring server.
Receives telemetry datagrams, tracks every node, raises application-level alerts
and publishes its view to state.json for the controller and the dashboard."""
import json
import socket
import threading
import time
from collections import deque

import jf_config as C

nodes = {}
lock = threading.Lock()
active = {}          # (node, kind) -> (level, text)


def alert(key, level, text):
    """Log only when an alert appears, changes level, or clears."""
    old = active.get(key)
    if level == "OK":
        if old:
            del active[key]
            C.log_line(C.COLLECTOR_ALERT_LOG, "[COLLECTOR] CLEARED  " + text)
        return
    if old is None or old[0] != level:
        C.log_line(C.COLLECTOR_ALERT_LOG, "[COLLECTOR] %-8s %s" % (level, text))
    active[key] = (level, text)


def receiver(sock):
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except OSError:
            return
        now = time.time()
        try:
            m = json.loads(data.decode())
            name = str(m["node"])
            seq = int(m["seq"])
            tx = float(m.get("tx_mbps", 0))
            rx = float(m.get("rx_mbps", 0))
            ts = float(m.get("ts", now))
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            continue                       # malformed datagram: ignore
        with lock:
            n = nodes.setdefault(name, {"last_seq": None, "last_seen": None, "received": 0,
                                        "lost": 0, "events": deque(), "tx": 0.0, "rx": 0.0,
                                        "delay_ms": 0.0})
            silent = n["last_seen"] is not None and now - n["last_seen"] > C.DOWN_AFTER_SEC
            lost_now = 0
            if n["last_seq"] is not None and seq > n["last_seq"] + 1 and not silent:
                lost_now = seq - n["last_seq"] - 1
            n["last_seq"] = seq
            n["last_seen"] = now
            n["received"] += 1
            n["lost"] += lost_now
            n["events"].append((now, lost_now))
            n["tx"], n["rx"] = tx, rx
            n["delay_ms"] = max(0.0, (now - ts) * 1000.0)


def evaluate_once():
    now = time.time()
    out_nodes = {}
    with lock:
        for name, n in nodes.items():
            while n["events"] and now - n["events"][0][0] > C.LOSS_WINDOW_SEC:
                n["events"].popleft()
            got = len(n["events"])
            lost = sum(e[1] for e in n["events"])
            total = got + lost
            loss_pct = 100.0 * lost / total if total else 0.0
            age = now - n["last_seen"]
            status = "DOWN" if age > C.DOWN_AFTER_SEC else "UP"

            if status == "DOWN":
                alert((name, "down"), "CRITICAL",
                      "%s node DOWN - no telemetry for %.0fs" % (name, age))
                for k in ("tx", "loss", "delay"):
                    active.pop((name, k), None)
            else:
                alert((name, "down"), "OK", "%s node back UP" % name)
                tx = n["tx"]
                if tx >= C.TX_CRIT_MBPS:
                    alert((name, "tx"), "CRITICAL",
                          "%s app-level TX %.1f Mbps >= %.1f" % (name, tx, C.TX_CRIT_MBPS))
                elif tx >= C.TX_WARN_MBPS:
                    alert((name, "tx"), "WARNING",
                          "%s app-level TX %.1f Mbps >= %.1f" % (name, tx, C.TX_WARN_MBPS))
                else:
                    alert((name, "tx"), "OK", "%s app-level TX back to normal" % name)
                if total >= 5 and loss_pct >= C.LOSS_WARN_PCT:
                    alert((name, "loss"), "WARNING",
                          "%s telemetry loss %.0f%% over last %ds" % (name, loss_pct, C.LOSS_WINDOW_SEC))
                else:
                    alert((name, "loss"), "OK", "%s telemetry loss back to normal" % name)
                if n["delay_ms"] >= C.DELAY_WARN_MS:
                    alert((name, "delay"), "WARNING",
                          "%s telemetry delay %.0f ms" % (name, n["delay_ms"]))
                else:
                    alert((name, "delay"), "OK", "%s telemetry delay back to normal" % name)

            out_nodes[name] = {"status": status, "tx_mbps": round(n["tx"], 2),
                               "rx_mbps": round(n["rx"], 2), "loss_pct": round(loss_pct, 1),
                               "delay_ms": round(n["delay_ms"], 1), "received": n["received"],
                               "lost": n["lost"], "age_s": round(age, 1)}
        alerts = ["%s %s" % (lv, tx_) for lv, tx_ in active.values()]
    C.write_json_atomic(C.STATE_FILE, {"updated": now, "nodes": out_nodes, "alerts": alerts})


def main():
    C.ensure_dir()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", C.TELEMETRY_PORT))
    print("collector listening on UDP %d" % C.TELEMETRY_PORT, flush=True)
    threading.Thread(target=receiver, args=(sock,), daemon=True).start()
    while True:
        evaluate_once()
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
```

4. `dashboard.py`. How it works: every second it reads `state.json` (server) and `net_state.json` (controller) and prints one combined table plus active alerts.

```python
#!/usr/bin/env python3
"""Terminal dashboard: merges collector (application) and controller (network) state."""
import time

import jf_config as C


def f(v, spec="{:.1f}"):
    return "-" if v is None else spec.format(v)


def render():
    app = C.read_json(C.STATE_FILE) or {}
    net = C.read_json(C.NET_STATE_FILE) or {}
    now = time.time()
    app_ok = bool(app) and now - app.get("updated", 0) < 5
    net_ok = bool(net) and now - net.get("updated", 0) < 6
    out = [time.strftime("=== SDN NETWORK MONITOR  %H:%M:%S ===")]
    out.append("collector: %s   controller: %s   mitigation: %s" % (
        "running" if app_ok else "NOT RUNNING", "running" if net_ok else "NOT RUNNING",
        ("ON" if net.get("mitigation") else "OFF") if net_ok else "-"))
    out.append("")
    out.append("%-5s %-5s %6s %6s %6s %7s | %6s %6s %6s  %s" % (
        "NODE", "APP", "TX", "RX", "LOSS%", "DLY ms", "SW-IN", "SW-OUT", "UTIL%", "NET-STATE"))
    app_nodes = app.get("nodes", {})
    net_hosts = net.get("hosts", {})
    for name in sorted(set(app_nodes) | set(net_hosts)):
        n = app_nodes.get(name, {})
        h = net_hosts.get(name, {})
        state = h.get("level", "-") + (" QUARANTINED" if h.get("quarantined") else "")
        out.append("%-5s %-5s %6s %6s %6s %7s | %6s %6s %6s  %s" % (
            name, n.get("status", "-"), f(n.get("tx_mbps")), f(n.get("rx_mbps")),
            f(n.get("loss_pct"), "{:.0f}"), f(n.get("delay_ms"), "{:.0f}"),
            f(h.get("ingress_mbps")), f(h.get("egress_mbps")), f(h.get("util_in_pct"), "{:.0f}"), state))
    out.append("")
    links = net.get("links", {})
    out.append("LINKS: " + (" | ".join("%s %.0f%% (%.1f Mbps)" % (k, v["util_pct"], v["mbps"])
                                       for k, v in sorted(links.items())) or "-"))
    out.append("QUARANTINED: " + (", ".join(net.get("quarantined", [])) or "-"))
    for dpid, flows in sorted(net.get("top_flows", {}).items()):
        busy = ["%s->%s %.2f Mbps" % (x["src"], x["dst"], x["mbps"]) for x in flows if x["mbps"] > 0.05]
        if busy:
            out.append("FLOWS s%s: %s  (entries: %s)" % (dpid, ", ".join(busy),
                                                         net.get("flow_entries", {}).get(str(dpid), "?")))
    out.append("")
    out.append("ACTIVE ALERTS:")
    alerts = app.get("alerts", []) + net.get("alerts", [])
    out.extend("  " + a for a in alerts) if alerts else out.append("  none")
    return "\n".join(out)


def main():
    while True:
        print("\033[2J\033[H" + render(), flush=True)
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
```

**Test (no Mininet needed)**: open 4 terminals in the folder.
```bash
python3 collector.py                                       # T1
python3 agent.py --name h1 --server 127.0.0.1              # T2
python3 agent.py --name h2 --server 127.0.0.1 --drop 0.5   # T3
python3 dashboard.py                                       # T4
```
Expected after ~15 s: dashboard shows h1 `UP` with loss 0 and h2 `UP` with loss around 50%; T1 prints `[COLLECTOR] WARNING h2 telemetry loss ...`. Press Ctrl+C in T2: after ~5 s `h1 node DOWN` appears. Stop everything, then run `sudo rm -rf /tmp/jackfruit`.

Then push: `git add jf_config.py agent.py collector.py dashboard.py && git commit -m "UDP side" && git pull --rebase && git push`

**Done when:** the test behaves as described and your files are pushed.
**You also do:** experiment E4 (Step 8) and the README section "UDP socket design" (Step 9).

---

## Step 5: Person B, the SDN controller

**What you are building (plain words):** the "brain" of the switches. It teaches switches to forward traffic (a *learning switch*), measures how busy every port is, compares that with the telemetry the server saved, raises alerts, and blocks a host that is confirmed to be flooding.

**Do first:** `git pull` to get `jf_config.py` from A (the controller imports it).

`controller.py`. How it works:
- **Learning switch:** unknown packets go to the controller (Packet-In); it remembers which port each MAC address is on and installs flow entries so later packets are forwarded by the switch alone.
- **Statistics:** every 2 s it sends port-stats and flow-stats requests; from the byte counters it computes Mbps and utilisation.
- **Decision (`_evaluate`):** applies the rules from Section 1 and keeps alerts from repeating.
- **Quarantine:** installs three flow entries on the host's switch: priority 100 = drop all, priority 150 = allow ARP, priority 200 = allow UDP to the telemetry port. Higher priority wins, so ARP and telemetry pass and everything else is dropped. `_release` deletes the three entries.
- **Port-Status:** a link going down raises a CRITICAL alert.
- **`MITIGATION=0`** disables blocking (this is the baseline for the comparison).
- The topology map at the top of the file (which host is on which switch port) must match `topo.py`; it already does.

```python
#!/usr/bin/env python3
"""Ryu OpenFlow 1.3 controller:
 - learning switch
 - periodic port + flow statistics (utilisation)
 - combines network statistics with application telemetry (state.json from collector)
 - raises alerts and automatically quarantines a confirmed abnormal sender.
Set MITIGATION=0 for the monitoring-only baseline."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jf_config as C  # noqa: E402

from ryu.base import app_manager  # noqa: E402
from ryu.controller import ofp_event  # noqa: E402
from ryu.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls  # noqa: E402
from ryu.lib import hub  # noqa: E402
from ryu.lib.packet import ether_types, ethernet, packet  # noqa: E402
from ryu.ofproto import ofproto_v1_3  # noqa: E402

MITIGATION = os.environ.get("MITIGATION", "1") != "0"

# Static map of the topology built in topo.py: host -> (switch dpid, switch port)
HOST_EDGE = {"h1": (2, 1), "h2": (2, 2), "h3": (3, 1), "h4": (3, 2), "h5": (1, 1)}
TRUNKS = {(2, 3): "s2-s1", (3, 3): "s3-s1"}      # edge-switch trunk ports (both directions)
SERVER_HOST = "h5"                                 # never quarantined
PRIO_LEARN, PRIO_DROP, PRIO_ARP, PRIO_TELEM = 1, 100, 150, 200


def mac_name(mac):
    if mac and mac.startswith("00:00:00:00:00:"):
        return "h%d" % int(mac.split(":")[-1], 16)
    return mac


class MonitorController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MonitorController, self).__init__(*args, **kwargs)
        C.ensure_dir()
        self.datapaths = {}
        self.mac_to_port = {}
        self.prev_ports = {}      # (dpid, port) -> (rx_bytes, tx_bytes, time)
        self.port_mbps = {}       # (dpid, port) -> (ingress Mbps, egress Mbps)
        self.prev_flows = {}
        self.top_flows = {}
        self.flow_count = {}
        self.hot = {}             # host -> consecutive CRITICAL polls
        self.quarantined = {}     # host -> earliest release time
        self.active = {}          # alert key -> (level, text)
        self.logger.info("Monitor controller started, mitigation=%s", MITIGATION)
        self.monitor_thread = hub.spawn(self._monitor_loop)

    # ------------------------------------------------------------ logging / alerts
    def _log(self, level, text):
        C.log_line(C.CONTROLLER_ALERT_LOG, "[CONTROLLER] %-8s %s" % (level, text))

    def _set_alert(self, key, label, level, text):
        old = self.active.get(key)
        if level == "OK":
            if old:
                del self.active[key]
                self._log("CLEARED", "%s back to normal" % label)
            return
        if old is None or old[0] != level:
            self._log(level, text)
        self.active[key] = (level, text)

    # ------------------------------------------------------------ switch handling
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _features(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self._add_flow(dp, 0, parser.OFPMatch(), actions)          # table-miss

    def _add_flow(self, dp, priority, match, actions, idle=0):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)] if actions else []
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority, match=match,
                                      instructions=inst, idle_timeout=idle))

    def _del_flow(self, dp, priority, match):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        dp.send_msg(parser.OFPFlowMod(datapath=dp, command=ofp.OFPFC_DELETE_STRICT,
                                      priority=priority, match=match,
                                      out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        in_port = msg.match["in_port"]
        eth = packet.Packet(msg.data).get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out_port = self.mac_to_port[dp.id].get(eth.dst, ofp.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_src=eth.src, eth_dst=eth.dst)
            self._add_flow(dp, PRIO_LEARN, match, actions, idle=30)
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                        in_port=in_port, actions=actions, data=data))

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        port = msg.desc.port_no
        if port > ofp.OFPP_MAX:
            return
        down = bool(msg.desc.state & ofp.OFPPS_LINK_DOWN) or bool(msg.desc.config & ofp.OFPPC_PORT_DOWN)
        label = "s%d port %d" % (dp.id, port)
        self._set_alert("port:%d:%d" % (dp.id, port), label,
                        "CRITICAL" if down else "OK", "LINK DOWN on %s" % label)

    # ------------------------------------------------------------ statistics
    def _request_stats(self, dp):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        dp.send_msg(parser.OFPPortStatsRequest(dp, 0, ofp.OFPP_ANY))
        dp.send_msg(parser.OFPFlowStatsRequest(dp))

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply(self, ev):
        dp = ev.msg.datapath
        now = time.time()
        for st in ev.msg.body:
            if st.port_no > dp.ofproto.OFPP_MAX:
                continue
            key = (dp.id, st.port_no)
            prev = self.prev_ports.get(key)
            if prev and now > prev[2]:
                dt = now - prev[2]
                self.port_mbps[key] = (max(st.rx_bytes - prev[0], 0) * 8 / dt / 1e6,
                                       max(st.tx_bytes - prev[1], 0) * 8 / dt / 1e6)
            self.prev_ports[key] = (st.rx_bytes, st.tx_bytes, now)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply(self, ev):
        dp = ev.msg.datapath
        now = time.time()
        rates = []
        for st in ev.msg.body:
            if st.priority != PRIO_LEARN:
                continue
            try:
                m = dict(st.match.items())
            except Exception:
                continue
            key = (dp.id, m.get("in_port"), m.get("eth_src"), m.get("eth_dst"))
            prev = self.prev_flows.get(key)
            self.prev_flows[key] = (st.byte_count, now)
            if prev and now > prev[1]:
                mbps = max(st.byte_count - prev[0], 0) * 8 / (now - prev[1]) / 1e6
                rates.append((mbps, mac_name(m.get("eth_src")), mac_name(m.get("eth_dst"))))
        rates.sort(reverse=True)
        self.top_flows[dp.id] = [{"src": s, "dst": d, "mbps": round(r, 2)} for r, s, d in rates[:3]]
        self.flow_count[dp.id] = len(ev.msg.body)

    # ------------------------------------------------------------ analysis
    def _read_telemetry(self):
        st = C.read_json(C.STATE_FILE)
        if not st or time.time() - st.get("updated", 0) > 5:
            return {}
        return st.get("nodes", {})

    def _monitor_loop(self):
        while True:
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)
            hub.sleep(C.POLL_SEC)
            try:
                self._evaluate()
            except Exception:
                self.logger.exception("evaluation failed")

    def _evaluate(self):
        now = time.time()
        telem = self._read_telemetry()
        hosts = {}
        for h, (dpid, port) in HOST_EDGE.items():
            pm = self.port_mbps.get((dpid, port))
            if pm is None:
                continue
            ing, egr = pm                      # ingress = host -> switch
            util_in = ing * 100.0 / C.LINK_BW_MBPS
            util_out = egr * 100.0 / C.LINK_BW_MBPS
            t = telem.get(h)
            agent_tx = t.get("tx_mbps") if (t and t.get("status") == "UP") else None
            level, text = "OK", ""
            if util_in >= C.UTIL_CRIT_PCT:
                if agent_tx is not None and agent_tx >= C.TX_CRIT_MBPS:
                    level = "CRITICAL"
                    text = ("%s CONFIRMED abnormal sender: switch sees %.1f Mbps in (%.0f%%), "
                            "agent reports TX %.1f Mbps" % (h, ing, util_in, agent_tx))
                elif agent_tx is None:
                    level = "WARNING"
                    text = "%s high ingress %.1f Mbps but NO telemetry from it" % (h, ing)
                else:
                    level = "WARNING"
                    text = ("%s MISMATCH: switch sees %.1f Mbps, agent reports only %.1f Mbps"
                            % (h, ing, agent_tx))
            elif util_in >= C.UTIL_WARN_PCT:
                level, text = "WARNING", "%s elevated ingress %.1f Mbps (%.0f%%)" % (h, ing, util_in)
            elif util_out >= C.UTIL_WARN_PCT:
                level, text = "WARNING", "%s heavy inbound traffic %.1f Mbps (%.0f%%)" % (h, egr, util_out)

            if h in self.quarantined and level != "OK":
                text += " [QUARANTINED]"
            self._set_alert("host:" + h, h, level, text)

            self.hot[h] = self.hot.get(h, 0) + 1 if level == "CRITICAL" else 0
            if MITIGATION and h != SERVER_HOST and h not in self.quarantined \
                    and self.hot[h] >= C.HOT_POLLS:
                self._quarantine(h)
            elif h in self.quarantined and now >= self.quarantined[h] and util_in < C.UTIL_WARN_PCT:
                self._release(h)

            hosts[h] = {"ingress_mbps": round(ing, 2), "egress_mbps": round(egr, 2),
                        "util_in_pct": round(util_in, 1), "level": level,
                        "quarantined": h in self.quarantined}

        links = {}
        for (dpid, port), name in TRUNKS.items():
            pm = self.port_mbps.get((dpid, port))
            if pm is None:
                continue
            mbps = max(pm)
            util = mbps * 100.0 / C.LINK_BW_MBPS
            lvl = "CRITICAL" if util >= C.UTIL_CRIT_PCT else ("WARNING" if util >= C.UTIL_WARN_PCT else "OK")
            self._set_alert("link:" + name, "link " + name, lvl,
                            "link %s CONGESTION %.0f%% utilised (%.1f Mbps)" % (name, util, mbps))
            links[name] = {"mbps": round(mbps, 2), "util_pct": round(util, 1), "level": lvl}

        C.write_json_atomic(C.NET_STATE_FILE, {
            "updated": now, "mitigation": MITIGATION, "hosts": hosts, "links": links,
            "quarantined": sorted(self.quarantined),
            "alerts": ["%s %s" % (lv, tx) for lv, tx in self.active.values()],
            "flow_entries": self.flow_count, "top_flows": self.top_flows})

    # ------------------------------------------------------------ mitigation
    def _quarantine_matches(self, parser, port):
        return [(PRIO_DROP, parser.OFPMatch(in_port=port)),
                (PRIO_ARP, parser.OFPMatch(in_port=port, eth_type=0x0806)),
                (PRIO_TELEM, parser.OFPMatch(in_port=port, eth_type=0x0800, ip_proto=17,
                                             udp_dst=C.TELEMETRY_PORT))]

    def _quarantine(self, host):
        dpid, port = HOST_EDGE[host]
        dp = self.datapaths.get(dpid)
        if dp is None:
            return
        parser = dp.ofproto_parser
        normal = [parser.OFPActionOutput(dp.ofproto.OFPP_NORMAL)]
        (p1, m1), (p2, m2), (p3, m3) = self._quarantine_matches(parser, port)
        self._add_flow(dp, p1, m1, [])          # drop everything from this host ...
        self._add_flow(dp, p2, m2, normal)      # ... except ARP
        self._add_flow(dp, p3, m3, normal)      # ... and telemetry to the monitoring server
        self.quarantined[host] = time.time() + C.QUARANTINE_SEC
        self._log("ACTION", "QUARANTINE %s: drop all traffic from s%d port %d except ARP and "
                            "telemetry (UDP %d)" % (host, dpid, port, C.TELEMETRY_PORT))

    def _release(self, host):
        dpid, port = HOST_EDGE[host]
        dp = self.datapaths.get(dpid)
        if dp is not None:
            for prio, match in self._quarantine_matches(dp.ofproto_parser, port):
                self._del_flow(dp, prio, match)
        self.quarantined.pop(host, None)
        self.hot[host] = 0
        self._log("ACTION", "RELEASE %s: traffic allowed again" % host)
```

**Test (standalone, no `topo.py` needed)**
```bash
# Terminal 1
ryu-manager --ofp-tcp-listen-port 6653 controller.py
# Terminal 2
sudo mn -c
sudo mn --controller=remote,ip=127.0.0.1,port=6653 --switch ovsk,protocols=OpenFlow13 --topo single,3 --mac
mininet> pingall
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
```
Expected: `pingall` shows `0% dropped`; `dump-flows` shows the table-miss flow plus learned flows; Terminal 1 shows `Monitor controller started, mitigation=True`. Then `exit` and `sudo mn -c`.

Push: `git add controller.py && git commit -m "Controller" && git pull --rebase && git push`

**Done when:** the test passes and `controller.py` is pushed. (Alerts and quarantine are verified in Step 7 because they need the full topology.)
**You also do:** experiment E2 (Step 8) and the README section "SDN controller design" (Step 9).

---

## Step 6: Person C, the Mininet topology and plot script

**What you are building (plain words):** the virtual network everything runs in, and the script that draws the comparison graph.

**Do first:** `git pull` to get `jf_config.py`.

1. `topo.py`. How it works: creates 3 switches and 5 hosts with fixed IPs/MACs, 10 Mbps links and **fixed port numbers** (the controller depends on them), connects to the Ryu controller on port 6653, waits for the switches to connect, runs a `pingall`, starts the collector on h5 and an agent on h1–h4, then opens the CLI (with our extra `agent` command). When you exit it stops the agents and the server.

```python
#!/usr/bin/env python3
"""Mininet topology + application launcher.   Run with: sudo python3 topo.py

            h5 (monitoring server 10.0.0.5)
             |
            s1 ---------- s3 -- h3, h4
             |
            s2 -- h1, h2
"""
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from mininet.cli import CLI  # noqa: E402
from mininet.link import TCLink  # noqa: E402
from mininet.log import info, setLogLevel  # noqa: E402
from mininet.net import Mininet  # noqa: E402
from mininet.node import OVSSwitch, RemoteController  # noqa: E402

import jf_config as C  # noqa: E402


def start_agent(node, drop="0"):
    node.cmd('python3 -u "%s/agent.py" --name %s --server %s --drop %s > %s/agent_%s.out 2>&1 &'
             % (BASE, node.name, C.SERVER_IP, drop, C.STATE_DIR, node.name))


class MonitorCLI(CLI):
    def do_agent(self, line):
        """agent <host> [drop 0-1] : restart the telemetry agent of a host (drop = share of datagrams not sent)"""
        parts = line.split()
        if not parts:
            print("usage: agent h1 0.4")
            return
        try:
            node = self.mn.get(parts[0])
            drop = str(float(parts[1])) if len(parts) > 1 else "0"
        except (KeyError, ValueError):
            print("usage: agent h1 0.4")
            return
        node.cmd("pkill -f 'agent.py --name %s'" % node.name)
        start_agent(node, drop)
        print("agent on %s restarted, drop=%s" % (node.name, drop))


def run():
    C.ensure_dir()
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=C.OFP_PORT)
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")
    s3 = net.addSwitch("s3", protocols="OpenFlow13")
    h = {}
    for i in range(1, 6):
        h[i] = net.addHost("h%d" % i, ip="10.0.0.%d/24" % i, mac="00:00:00:00:00:%02x" % i)
    bw = C.LINK_BW_MBPS
    # explicit port numbers: controller.py relies on them
    net.addLink(h[5], s1, port1=0, port2=1, bw=bw)
    net.addLink(s1, s2, port1=2, port2=3, bw=bw)
    net.addLink(s1, s3, port1=3, port2=3, bw=bw)
    net.addLink(h[1], s2, port1=0, port2=1, bw=bw)
    net.addLink(h[2], s2, port1=0, port2=2, bw=bw)
    net.addLink(h[3], s3, port1=0, port2=1, bw=bw)
    net.addLink(h[4], s3, port1=0, port2=2, bw=bw)
    net.start()
    try:
        try:
            ok = net.waitConnected(timeout=15)
        except AttributeError:
            time.sleep(3)
            ok = True
        if not ok:
            info("*** WARNING: switches did not connect - is ryu-manager running?\n")
        net.pingAll()

        h[5].cmd('python3 -u "%s/collector.py" > %s/collector.out 2>&1 &' % (BASE, C.STATE_DIR))
        time.sleep(1)
        for i in range(1, 5):
            start_agent(h[i])
        info("*** Collector on h5 and telemetry agents on h1-h4 started\n")
        info("*** Extra CLI command:  agent <host> <drop 0-1>\n")
        MonitorCLI(net)
    finally:
        subprocess.call(["pkill", "-f", "agent.py --name"])
        subprocess.call(["pkill", "-f", "collector.py"])
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
```

2. `plot_results.py`. How it works: reads the two `iperf` server logs from experiment E3 (mitigation OFF and ON), turns each into "Mbps per second", prints the average during the attack and saves a graph in `results/victim_throughput.png`.

```python
#!/usr/bin/env python3
"""Compare victim throughput with mitigation OFF (baseline) and ON.
Usage: python3 plot_results.py [victim_OFF.txt] [victim_ON.txt]
Needs the iperf server logs created with:  iperf -s -u -p 5002 -i 1 > file"""
import os
import re
import sys

PAT = re.compile(r"(\d+\.\d+)\s*-\s*(\d+\.\d+)\s+sec\s+[\d.]+\s+\S+\s+([\d.]+)\s+([KMG]?)bits/sec")
ATTACK_START, ATTACK_END = 10, 30          # seconds of the experiment (see plan)


def load(path):
    d = {}
    for line in open(path):
        m = PAT.search(line)
        if not m:
            continue
        start, end, val, unit = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4)
        if end - start > 1.5:              # skip the final whole-run summary line
            continue
        d[int(round(end))] = val * {"": 1e-6, "K": 1e-3, "M": 1.0, "G": 1e3}[unit]
    n = max(d) if d else 0
    return [d.get(i, 0.0) for i in range(1, n + 1)]


def mean_attack(series):
    w = [series[i - 1] if i - 1 < len(series) else 0.0 for i in range(ATTACK_START + 1, ATTACK_END + 1)]
    return sum(w) / len(w)


def main():
    off = sys.argv[1] if len(sys.argv) > 1 else "/tmp/jackfruit/victim_OFF.txt"
    on = sys.argv[2] if len(sys.argv) > 2 else "/tmp/jackfruit/victim_ON.txt"
    s_off, s_on = load(off), load(on)
    print("Mean victim throughput during attack window (t=%d-%ds):" % (ATTACK_START, ATTACK_END))
    print("  mitigation OFF (baseline): %.2f Mbps" % mean_attack(s_off))
    print("  mitigation ON  (proposed): %.2f Mbps" % mean_attack(s_on))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - table only")
        return
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    plt.figure(figsize=(8, 4))
    plt.plot(range(1, len(s_off) + 1), s_off, label="mitigation OFF (baseline)")
    plt.plot(range(1, len(s_on) + 1), s_on, label="mitigation ON (proposed)")
    plt.axvspan(ATTACK_START, ATTACK_END, color="red", alpha=0.1, label="flood active")
    plt.xlabel("time (s)")
    plt.ylabel("victim throughput (Mbps)")
    plt.ylim(0, 5)
    plt.legend()
    plt.tight_layout()
    path = os.path.join(out_dir, "victim_throughput.png")
    plt.savefig(path, dpi=150)
    print("saved", path)


if __name__ == "__main__":
    main()
```

Push: `git add topo.py plot_results.py && git commit -m "Topology and plot" && git pull --rebase && git push`

**Done when:** both files are pushed. They are fully tested in Step 7.
**You also do:** experiments E1 and E3 (Step 8), and lead Step 9.

---

## Step 7: Put it all together and run the smoke test (everyone, C leads)

First everyone runs `git pull` so all 7 files are in one folder (`jf_config.py agent.py collector.py dashboard.py controller.py topo.py plot_results.py`). One person runs it; the others can repeat it on their own VM. Open 3 terminals in the folder.

```bash
# T1: controller (always start FIRST)
sudo mn -c; sudo rm -rf /tmp/jackfruit
ryu-manager --ofp-tcp-listen-port 6653 controller.py

# T2: network and apps (the mininet> prompt opens)
sudo python3 topo.py

# T3: live dashboard
python3 dashboard.py

# optional T4: live alerts
tail -F /tmp/jackfruit/alerts_controller.log /tmp/jackfruit/alerts_collector.log
```
**Expected:** T2 prints `0% dropped` for `pingall` and "Collector on h5 and telemetry agents on h1-h4 started". After ~5 s the dashboard shows h1 to h4 `UP`, SW-IN/SW-OUT near 0, no alerts.

**Smoke test (this proves the project works end to end).** At the `mininet>` prompt:
```
h4 iperf -s -u -p 5001 > /dev/null &
h3 iperf -c 10.0.0.4 -u -b 9M -t 20 -p 5001
```
(This makes h3 flood h4 with 9 Mbps of UDP for 20 s.)

**Expected within ~5 s:** the controller prints `CRITICAL h3 CONFIRMED abnormal sender ...` and then `ACTION QUARANTINE h3 ...`; the server prints `CRITICAL h3 app-level TX ...`; the dashboard shows h3 as `CRITICAL QUARANTINED`. After the flood stops, `RELEASE h3` appears. (An iperf warning "did not receive ack" is normal, because the quarantine drops the traffic.) Finally run `h4 pkill iperf`.

**Cleanup between runs:** type `exit` in the CLI, then `sudo mn -c`.

**Done when:** the smoke test shows the alert, the quarantine and the release. If anything differs, go to the Troubleshooting section at the end.

---

## Step 8: Experiments (these give the results for "Performance Evaluation & Comparison")

Record all numbers in `results/results.md` and push. Log lines look like `HH:MM:SS.mmm`; **detection time = first alert time minus the start time printed by `date`**. Always start each experiment from a clean state (Step 7 cleanup, then start T1, T2, T3 again). Create the iperf servers inside the CLI exactly as shown.

### E1 (Person C): normal operation
Leave the system idle for 60 s with `h1 ping -c 20 10.0.0.2` running in the CLI. Record from the dashboard: number of alerts (expected **0**), telemetry loss (0%), telemetry delay (a few ms). This shows there are no false alarms.

### E2 (Person B): detection at three flood rates
```
h4 iperf -s -u -p 5001 > /dev/null &
h3 date +%T.%3N
h3 iperf -c 10.0.0.4 -u -b 3M -t 20 -p 5001
```
Repeat with `-b 6M` and `-b 9M` (wait ~20 s between runs so the quarantine is released). Record for each rate: alerts raised, their level, detection time, whether the host was quarantined. **Expected:** 3M gives no alert, 6M gives WARNING only (no quarantine), 9M gives CRITICAL plus quarantine in about 4 to 6 s. Find the times with:
```bash
grep -E "CRITICAL|WARNING|ACTION" /tmp/jackfruit/alerts_controller.log
```
This shows the thresholds work and the system only blocks when it is sure.

### E3 (Person C): baseline vs proposed (the main comparison)
A normal 4 Mbps "victim" flow (h1 to h4) runs for 40 s. From second 10 to 30, h2 floods h3 at 10 Mbps. Both flows cross the same link between s2 and s1, so the victim suffers unless the flood is stopped.

Run it **twice**:
- **Run OFF (baseline, watch only):** start the controller with `MITIGATION=0 ryu-manager --ofp-tcp-listen-port 6653 controller.py`
- **Run ON (proposed):** start the controller normally

In both runs, in the CLI (use `victim_ON.txt` in the second run):
```
h3 iperf -s -u -p 5001 > /dev/null &
h4 iperf -s -u -p 5002 -i 1 > /tmp/jackfruit/victim_OFF.txt &
h1 iperf -c 10.0.0.4 -u -b 4M -t 40 -p 5002 > /dev/null &
sh sleep 10
h2 iperf -c 10.0.0.3 -u -b 10M -t 20 -p 5001 > /dev/null &
sh sleep 35
h4 pkill iperf
h3 pkill iperf
```
Then:
```bash
python3 plot_results.py
mkdir -p results
cp /tmp/jackfruit/victim_*.txt /tmp/jackfruit/alerts_*.log results/
```
Record: the average victim throughput during the attack (printed by the script), the final loss % from the summary line in each `victim_*.txt`, and the graph `results/victim_throughput.png`. **Expected:** the baseline victim loses roughly 25 to 30% during the flood; with mitigation it recovers within a few seconds. (These are estimates; report what you actually measure.)

### E4 (Person A): robustness (challenging scenarios)
In the CLI, with the system idle:

| Scenario | Commands | Expected |
|---|---|---|
| Telemetry packet loss | `agent h1 0.4`, wait 15 s, then `agent h1 0` | `[COLLECTOR] WARNING h1 telemetry loss`, then `CLEARED` |
| Link failure | `link s1 s3 down`, wait 10 s, then `link s1 s3 up` | controller `CRITICAL LINK DOWN` for s1/s3 port 3; server shows `h3` and `h4` `DOWN` after ~5 s; `CLEARED` / `back UP` after the link returns |
| Node/agent failure | `h2 pkill -f "agent.py --name h2"`, wait 8 s, then `agent h2 0` | `h2 node DOWN`, then `back UP` |

Record the detection time for each.

**Done when:** `results/results.md`, the graph and the logs are pushed to the repo.

---

## Step 9: Submission and demo (C leads, everyone writes their part)

### Final repo check (the repo exists since Step 3)
```
jackfruit-sdn-monitor/
  README.md  jf_config.py  agent.py  collector.py  dashboard.py
  controller.py  topo.py  plot_results.py
  results/   (results.md, victim_throughput.png, logs, screenshots)
```
Each person commits their own files with their own git name so every contribution is visible. Check that a fresh `git clone` followed by Steps 2 and 7 works (this is "reproducible").

### README.md must contain (each person writes their own section)
1. Problem statement and objectives
2. Architecture diagram and data flow (copy from Section 1)
3. UDP socket design: message format, sequence numbers, loss and delay detection, threads, error handling (**A**)
4. SDN controller design: statistics polling, utilisation formula, combined detection logic, quarantine flows with priorities 100/150/200, port-status handling (**B**)
5. Mininet topology, how to launch everything, how to reproduce (setup from Steps 1 to 2, run commands from Step 7) (**C**)
6. Test cases table (below)
7. Results of E1 to E4 with the graph and the baseline comparison (**C**, with numbers from all)
8. Limitations: fixed topology map in the controller, fixed thresholds, 2 s polling granularity, the controller reads the server's `state.json` file (shared file) instead of a socket

### Test cases table (fill the "Result" column from your runs)
| # | Test | Expected | Result |
|---|---|---|---|
| T1 | `pingall` | 0% dropped | |
| T2 | Idle, all agents running | 4 nodes UP, no alerts | |
| T3 | Flood 3M | no alert | |
| T4 | Flood 6M | WARNING only | |
| T5 | Flood 9M | CRITICAL + quarantine, telemetry still arrives | |
| T6 | Flood stops | RELEASE, alerts CLEARED | |
| T7 | Telemetry loss 40% | loss WARNING | |
| T8 | Link s1-s3 down/up | LINK DOWN, nodes DOWN, recovery | |
| T9 | Agent killed/restarted | DOWN then UP | |
| T10 | Victim under congestion, mitigation OFF vs ON | ON recovers | |

### Rubric → evidence (what to show for each mark)
| Rubric item | Deliverable | Show |
|---|---|---|
| Problem understanding & architecture | D1 (2) | README sections 1-2, diagram |
| UDP socket implementation | D1 (4) | `agent.py`, `collector.py`; malformed packet handling, seq numbers, threads |
| Mininet + SDN | D1 (4) | `topo.py`, `controller.py`, `ovs-ofctl dump-flows` |
| Socket–SDN integration | D1 (3) | controller reading `state.json` and the "CONFIRMED abnormal sender" alert |
| Initial testing & demo | D1 (2) | smoke test (Step 7) |
| Complete functionality | D2 (4) | dashboard with 4 nodes, alerts |
| Dynamic SDN | D2 (6) | quarantine/release flows appear and disappear in `dump-flows` |
| Challenging scenario | D2 (4) | E4 and E3 |
| Performance & comparison | D2 (5) | E2, E3 graph, tables |
| Documentation, demo, viva | D2 (6) | README, repo, Step 10 |

### Final demo script (4 terminals, same as Step 7)
1. Start the controller, `topo.py`, the dashboard and the log tail; show `pingall 0%` and 4 nodes UP.
2. Show the normal state: no alerts, low utilisation.
3. 6M flood from h3: WARNING only. 9M flood: CRITICAL and quarantine; show `sh ovs-ofctl -O OpenFlow13 dump-flows s3` with the priority 100/150/200 entries; show the release afterwards.
4. Show the victim graph (E3) and explain baseline vs proposed.
5. `agent h1 0.4` (telemetry loss), then `link s1 s3 down` and `link s1 s3 up`.
6. Open the repo and walk through the README results.

---

## Step 10: Viva preparation (everyone)

**Everyone (all files at overview level):** the architecture and data flow in Section 1; why UDP for telemetry (small, periodic, tolerant to loss, no connection overhead) and what you lose (no ordering, no retransmission, no delivery guarantee); the thresholds and why; the baseline comparison result. Read your own files line by line until you can say what each function does and why.

**UDP/sockets (A):** `socket(AF_INET, SOCK_DGRAM)`, `bind`, `sendto`, `recvfrom`; datagram boundaries (one send = one receive); UDP vs TCP; sequence numbers to detect loss; how loss % over a 10 s window is computed; the node DOWN rule (5 s silence); why the server uses a receiver thread plus an evaluation loop and a lock; error handling (malformed JSON ignored, `OSError` caught in the agent); atomic JSON write (`os.replace`); delay measurement (one-way, same clock inside Mininet).

**SDN/OpenFlow (B):** control plane vs data plane; what a controller does; OpenFlow 1.3 messages: Packet-In, Packet-Out, Flow-Mod, Port-Stats and Flow-Stats request/reply, Port-Status; table-miss entry; match + action + priority + idle timeout; learning-switch logic; utilisation formula `Δbytes × 8 / Δt / capacity`; why the switch's ingress counter still counts packets that a drop rule discards; the combined decision logic and its 3 outcomes (confirmed, mismatch, no telemetry); quarantine flows: why priorities 100 (drop), 150 (ARP), 200 (telemetry) and the `NORMAL` action; strict delete on release; why h5 is never quarantined; why 2 consecutive CRITICAL checks are required (avoid reacting to a spike).

**Mininet (C):** hosts are network namespaces, links are veth pairs, switches are Open vSwitch; `TCLink` with `bw=10` (speed limiting); explicit port numbers and fixed MACs and why the controller depends on them; `RemoteController`; start order (controller first); `sudo mn -c`; how iperf generated the flood and victim traffic; how E3 was run and what the graph shows; limitations.

**Likely questions with short answers**
- *Why does the controller need telemetry if it has flow statistics?* Flow statistics show the traffic, telemetry shows what the host itself reports; agreement gives confidence (confirmed), disagreement reveals spoofing, unmonitored traffic or a dead agent.
- *Why not block h3 completely?* Then monitoring would lose visibility; telemetry and ARP are exempted.
- *What if telemetry messages are lost?* Detected via sequence gaps; one lost message is harmless because the next arrives 1 s later.
- *How is the baseline defined?* The same controller with `MITIGATION=0`: it still monitors and alerts but never blocks.
- *What does a link-down look like to the controller?* An OpenFlow Port-Status message with the LINK_DOWN flag.
- *How do the sockets and the SDN controller interact?* The controller reads the server's `state.json` and its alerts change flow entries (quarantine).

---

## Troubleshooting (common problems only)
| Problem | Fix |
|---|---|
| `Unable to contact the remote controller` or switches not connecting | start `ryu-manager` first and check it is running; `sudo mn -c`, then rerun `topo.py` |
| `Address already in use` (port 6653) | an old controller is running: `pkill -f ryu-manager` |
| Stale interfaces or odd Mininet errors | `sudo mn -c` |
| `iperf: command not found` | `sudo apt install -y iperf` |
| Dashboard shows "NOT RUNNING" | the server starts only through `topo.py`; the controller must be running too |
| Permission denied writing `/tmp/jackfruit` | `sudo rm -rf /tmp/jackfruit`, then start the controller first |
| `ryu-manager` import error mentioning eventlet | use the apt `python3-ryu` package, or the venv fallback in Step 2 |
| `git push` rejected | run `git pull --rebase` first, then `git push` |
