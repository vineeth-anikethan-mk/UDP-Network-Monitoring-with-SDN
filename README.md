# Jackfruit: UDP Network Monitoring with SDN

This simplified project implements Topic 6: four hosts send UDP telemetry to a
central server. An SDN controller compares host reports with switch port and flow
statistics, raises alerts, and optionally quarantines a confirmed heavy sender.
A small Tkinter table displays the current state.

## Architecture

```mermaid
flowchart TD
    C["OS-Ken controller, TCP 6653"] -. OpenFlow 1.3 .-> S1[s1]
    C -. OpenFlow 1.3 .-> S2[s2]
    C -. OpenFlow 1.3 .-> S3[s3]
    S1 --- H5["h5: UDP collector, port 9999"]
    S1 --- S2
    S1 --- S3
    S2 --- H1[h1]
    S2 --- H2[h2]
    S3 --- H3[h3]
    S3 --- H4[h4]
```

All links are 10 Mbps. h1–h4 run agents; h5 is the collector. Addresses are
10.0.0.1–10.0.0.5. Host ports: h1=s2:1, h2=s2:2, h3=s3:1, h4=s3:2, h5=s1:1.
Trunks: s1:2–s2:3 and s1:3–s3:3.

## Setup and launch

Designed for Ubuntu with Mininet, Open vSwitch and Python 3. Ubuntu 26.04's
Python 3.14 uses the supplied pinned OS-Ken dependencies. OS-Ken is a Ryu fork;
the assignment does not mandate a specific framework. Do not install python3-ryu
or use ryu-manager for this version.

In this folder, as your normal user:

```bash
bash setup.sh
```

Setup installs Ubuntu packages and creates `.venv` for the controller. System
Python runs Mininet, collector, agents, UI and plotting. Do not use sudo pip.

Open three terminals in this folder:

```bash
# Terminal 1: leave running
bash controller.sh on
```

```bash
# Terminal 2: creates the network and starts the UDP applications
sudo python3 topology.py
```

```bash
# Terminal 3: simple desktop UI, without sudo
python3 dashboard.py
```

Expected: startup pingall has 0% loss and four agents become UP. A brief startup
DOWN state is possible before the first report. The collector and controller
publish separate JSON files under `/tmp/jackfruit_simple`. Atomic replacement
prevents partial reads. This shared filesystem is the application–SDN boundary;
telemetry itself travels over real UDP sockets in Mininet.

Stop by typing `exit` at `mininet>`, stopping the controller with Ctrl+C, closing
the UI, and running `sudo mn -c`. Only run cleanup when no other Mininet lab is
active. Always stop the topology before restarting the controller.

## Source files

| File | Purpose |
|---|---|
| config.py | Topology mapping, thresholds, JSON read/write |
| agent.py | Read interface byte counters and send UDP reports |
| collector.py | Validate reports, receive concurrently, publish UP/DOWN |
| controller.py | Install rules, read counters, decide and enforce quarantine |
| run_controller.py | OS-Ken startup adapter |
| topology.py | Build the network, launch processes and run experiments |
| dashboard.py | One table with live status, rates and alerts |
| plot_results.py | Graph and compare measured receiver throughput |
| test_project.py | Decision and protocol-encoding checks |
| requirements.txt | Pinned controller dependencies; not student application code |

## Socket design

Each JSON UDP datagram has `node`, `tx`, and `rx`. TX and RX are Mbps calculated
from `/proc/net/dev` byte-counter changes over monotonic elapsed time. Reports
arrive once a second. UDP is connectionless: sendto/recvfrom carry individual
messages without a handshake. One receiver thread handles reports from all hosts;
the main thread publishes state every second. A lock protects the shared nodes
dictionary. Malformed payloads, wrong source IPs and nonfinite/negative rates are
rejected. A host is DOWN after five seconds without a valid report.

This version deliberately does not calculate telemetry packet loss, one-way
delay, packet rates or sequence history. These are not required by Topic 6.
Robustness is demonstrated through link failure and recovery instead.

## SDN design

Each switch receives three priority-1 rules, matching ingress ports 1, 2 and 3,
with action OVS NORMAL. OVS performs standard MAC learning and forwarding. The
controller does not implement its own Packet-In learning switch. This is still
SDN control: OpenFlow installs forwarding rules, requests counters and dynamically
adds/removes high-priority filtering rules.

Every two seconds the controller requests port and flow statistics. Port ingress
Mbps = delta rx_bytes × 8 / elapsed_seconds / 1,000,000. Utilization = ingress
Mbps / 10 × 100. Flow Mbps sums byte-rate changes for rules on that host ingress
port, including quarantine drop and exemption rules. Rules are identified by
port and priority because this lab exclusively owns a single table and uses one
rule per priority on each ingress. Do not install unrelated rules in this lab.
Multipart replies are combined before calculating totals; new/reset flows need
another sample. Disconnected/stale counters cannot confirm a sender.

| Condition | Response |
|---|---|
| Fresh ingress below 5 Mbps | OK |
| Fresh ingress at least 5 Mbps | WARNING |
| Fresh ingress, flow rate and UP agent TX all at least 7 Mbps | CRITICAL |
| Two critical evaluations with new port AND flow samples; mitigation ON | Quarantine |
| At least 15 seconds blocked, ingress and fresh agent TX below 5 Mbps | Release |
| Missing/stale network statistics | UNKNOWN |

Quarantine priorities: 100 drops the host's ingress; 150 allows ARP; 200 allows
IPv4 UDP to collector 10.0.0.5:9999. Higher priority wins. Release deletes exactly
these rules. Port counters still measure packets arriving before they are
dropped. The collector remains reachable from a quarantined sender.

Mitigation OFF uses the same forwarding/monitoring logic without installing
quarantine rules. This is the baseline for performance comparison.

## Reproduce tests and experiments

Unit checks (controller need not run):

```bash
.venv/bin/python -m unittest -v test_project.py
```

In Mininet, record `nodes`, `net`, `dump`, and `pingall`. Idle for 60 seconds and
capture the UI. Then run each traffic rate separately:

```text
flood 3
sh sleep 30
flood 6
sh sleep 30
flood 9
sh sleep 8
sh ovs-ofctl -O OpenFlow13 dump-flows s3
sh sleep 30
```

Expected: 3 Mbps stays below threshold; 6 Mbps warns; 9 Mbps can confirm and
quarantine once all measurements agree. The flood runs for 20 seconds. Observe
continuing agent UP and increasing `seen` timestamps during quarantine, and
subsequent RELEASE. Timing depends on polling and VM load.

Failure/recovery, on an idle topology:

```text
link s1 s3 down
sh sleep 10
link s1 s3 up
sh sleep 10
```

h3/h4 should become DOWN and recover; h1/h2 should remain UP. This version uses
telemetry timeout to report this failure, not a separate physical-link alert.
It does not reroute: there is only one path.

For the baseline, stop the topology and controller, clean up with `sudo mn -c`,
then start `bash controller.sh off` and `sudo python3 topology.py` in separate
terminals. Wait at least six seconds, then at `mininet>`:

```text
compare OFF
```

Wait about 44 seconds for completion. Stop and clean up again. Start a fresh
controller with `bash controller.sh on`, start the topology, wait at least six
seconds, then:

```text
compare ON
```

h1 sends a 4 Mbps victim stream to h4 for 40 seconds. h2 sends 10 Mbps to h3
approximately from seconds 10–30. Both cross s2–s1, creating competition. Each
run saves receiver logs, sender logs, launch timing and snapshots in a timestamped
folder. Run in a normal terminal in this folder:

```bash
python3 plot_results.py
```

Outputs: results/victim_throughput.png, throughput_samples.csv and comparison.json.
The script compares the latest OFF/ON folders. Optional positional arguments
select exact OFF and ON victim.txt paths. Mean receiver goodput uses seconds
10–30 of receiver interval time; launch timing has a small alignment difference.
Missing intervals are errors, not invented zeros. Iperf final loss is whole-run
loss, not attack-window loss. Repeat pairs if time permits and report variation.

## Requirements and submission

| Requirement | Evidence |
|---|---|
| UDP agents + central server + multiple nodes | agent.py, collector.py, four UP rows |
| SDN flow stats + utilization + thresholds + alerts | controller.py, dashboard, logs |
| Combine telemetry and flow measurements | Three-measurement confirmation condition |
| Mininet + dynamic SDN | topology.py, quarantine flow dump and release |
| Challenging scenario | Link down/up and congestion |
| Performance comparison | Measured OFF/ON plot and logs |
| Documentation, code, config, tests, reproduction | This folder |
| Final GitHub demo | Upload this folder's contents and your measured evidence |

Fill RESULTS.md and save screenshots into results/. Upload the contents of
submit/ through GitHub's website (Add file → Upload files), excluding `.venv`,
`__pycache__` and bytecode. Do not upload only the ZIP. Each member should describe
actual contributions truthfully. The separate prepare/ folder is a personal
study guide; everything required to reproduce the submission is in this folder.

## Validation and limitations

The simplified version has 11 unit tests covering report validation/timeouts,
normal forwarding rule encoding, confirmation, stale/mismatched evidence, OFF
mode, hold/release, disconnect probes, multipart flow sums and incomplete plot
windows. Build checks and their exact outcomes appear in prepare/START_HERE.md.
Real Mininet/OVS behavior and performance must be verified on the Ubuntu VM.
Earlier logs from the larger project do not validate this changed controller.

Fixed topology, capacity and thresholds; legitimate heavy traffic can be blocked.
UDP is not authenticated or reliable; spoofed/replayed reports are not prevented.
Source-IP checking is validation, not security. Shared JSON assumes one machine.
Congestion can delay telemetry and prevent confirmation. Polling adds response
latency; counters include overhead and may briefly exceed link capacity. h5 and
trunks are not displayed in the simplified UI. Agent loss/delay histories and
switch flow listings were removed. UI closing does not stop the network. If the
controller dies, existing switch rules can remain: stop and restart the full lab.
