# Results — complete using your own Ubuntu runs

No measured Mininet results are supplied. Fill this before submission.

Run date: ______   Ubuntu/Python: ______   VM RAM/CPU: ______

| Test | Expected | Actual result | Screenshot/log |
|---|---|---|---|
| pingall | 0% loss | Pending | |
| Idle 60 seconds | Four UP, low traffic | Pending | |
| flood 3 | No sustained warning | Pending | |
| flood 6 | Warning, no quarantine | Pending | |
| flood 9 | CRITICAL then QUARANTINE | Pending | |
| Flow dump during quarantine | Priorities 100/150/200 | Pending | |
| Telemetry during quarantine | h3 UP, seen timestamp advances | Pending | |
| After flood | RELEASE after minimum hold, recovery | Pending | |
| Link down/up | h3/h4 DOWN then UP; h1/h2 stay UP | Pending | |
| OFF comparison | Baseline receiver throughput | Pending | |
| ON comparison | Mitigation receiver throughput | Pending | |

OFF attack-window mean Mbps: ______
ON attack-window mean Mbps: ______
Difference (ON minus OFF): ______
Whole-run iperf loss OFF / ON: ______ / ______
Time from flood start to confirmation / quarantine: ______ / ______

Explain what the data shows, including if mitigation did not improve it: ______
Limitations, startup artifacts, failures and repetitions: ______

Suggested screenshot filenames under results/:
01_topology.png, 02_normal.png, 03_warning.png, 04_quarantine.png,
05_flow_rules.png, 06_telemetry_continues.png, 07_release.png,
08_failure.png, 09_recovery.png, 10_comparison.png.

Controller logs are automatically saved in results/controller_*.log. Collector
and agent logs are in results/demo_*/. Flood logs there are overwritten by the
next flood, so take screenshots or copy those logs if needed before another run.
OFF/ON folders are separate and retain their experiment logs.
