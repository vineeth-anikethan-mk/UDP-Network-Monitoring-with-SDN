#!/usr/bin/env python3
"""Plot measured iperf2 receiver throughput; fail on incomplete attack windows."""
import argparse
import csv
import json
from pathlib import Path
import re
PAT = re.compile(r'(\d+\.\d+)\s*-\s*(\d+\.\d+)\s+sec\s+[\d.]+\s+\S+\s+([\d.]+)\s+([KMG]?)bits/sec')


def load(path):
    rows = {}
    for line in Path(path).read_text(errors='replace').splitlines():
        match = PAT.search(line)
        if not match:
            continue
        start, end, val = map(float, match.group(1,2,3))
        if 0 < end-start <= 1.5:
            rows[(start,end)] = val * {'':1e-6, 'K':1e-3, 'M':1., 'G':1e3}[match.group(4)]
    if not rows:
        raise ValueError(f'No interval samples in {path}; use receiver: iperf -s -u -i 1')
    return [(a,b,v) for (a,b),v in sorted(rows.items())]


def mean_attack(rows, start=10., end=30.):
    total = weight = 0.
    last = start
    for a,b,v in rows:
        overlap = max(0., min(b,end)-max(a,start))
        if overlap:
            if a > last+.05:
                raise ValueError('Missing intervals in the attack window; repeat experiment')
            if a < last-.05 and last > start:
                raise ValueError('Overlapping intervals; use one receiver stream per file')
            total += overlap*v
            weight += overlap
            last = b
    if abs(weight-(end-start)) > .1:
        raise ValueError('Incomplete attack window; missing samples are not treated as zero')
    return total/weight


def latest(label):
    paths = sorted((Path(__file__).resolve().parent/'results').glob(f'{label}_*/victim.txt'))
    if not paths:
        raise ValueError(f'No {label} results. In Mininet run: compare {label}')
    return paths[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('off', nargs='?')
    ap.add_argument('on', nargs='?')
    args = ap.parse_args()
    paths = [Path(args.off) if args.off else latest('OFF'), Path(args.on) if args.on else latest('ON')]
    series = [load(path) for path in paths]
    means = [mean_attack(rows) for rows in series]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dest = Path(__file__).resolve().parent/'results'
    dest.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10,5))
    for rows, label, color in zip(series, ('OFF — baseline','ON — mitigation'), ('#dd6b55','#167d9a')):
        ax.plot([b for a,b,v in rows], [v for a,b,v in rows], label=label, color=color, linewidth=2)
    ax.axvspan(10,30,color='#dd6b55',alpha=.12,label='Flood scheduled')
    ax.set(xlabel='Seconds from victim stream start',ylabel='Receiver throughput (Mbps)',ylim=(0,None),
           title='Jackfruit SDN: measured victim throughput\nNavneet Sai Murali | PES1UG25AM503')
    ax.grid(alpha=.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(dest/'victim_throughput.png',dpi=180)
    plt.close(fig)
    with (dest/'throughput_samples.csv').open('w',newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['mode','start_s','end_s','received_mbps'])
        for label,rows in zip(('OFF','ON'),series):
            writer.writerows((label,*row) for row in rows)
    summary = dict(attack_window_seconds=[10,30], off_mean_mbps=means[0],on_mean_mbps=means[1],
                   absolute_improvement_mbps=means[1]-means[0],
                   sources=[str(path) for path in paths],
                   note='Window relative to victim receiver intervals; see timing.txt for launch timing.')
    (dest/'comparison.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    print('Saved results/victim_throughput.png and throughput_samples.csv')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc))
