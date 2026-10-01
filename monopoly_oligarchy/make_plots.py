#!/usr/bin/env python3
"""
Monopoly simulation plots: ending net worth vs starting stake.
Run from the monopoly_oligarchy directory.

Produces one PNG per configuration with all players on the same axes.
"""

import subprocess
import csv
import io
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ── configurations ────────────────────────────────────────────────────────────
CONFIGS = [
    ("Equal Stakes",     "equal",        [1500, 1500, 1500, 1500, 1500, 1500]),
    ("Oligarchy Stakes", "oligarchy",    [  10,   10,   10,  100,  100, 8770]),
    ("Company Town",     "company_town", [   1,    1,    1,    1,    1, 8995]),
]

N_GAMES = 1000        # set to 1000 for the real run
JOBS    = 8
SEED    = 0

# six visually distinct marker/color pairs
MARKERS = ['o', 's', '^', 'D', 'v', 'P']
COLORS  = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

# ── simulation ────────────────────────────────────────────────────────────────

def run_sim(stakes):
    """Run the simulator and return per-game rows as a list of dicts."""
    cmd = [
        sys.executable, '-m', 'monopoly.simulate',
        *map(str, stakes),
        '-n', str(N_GAMES),
        '--csv', '-',
        '-j', str(JOBS),
        '-q',
        '--seed', str(SEED),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    # The summary table is appended after a blank line — keep only the CSV block.
    csv_block = result.stdout.split('\n\n')[0]
    return list(csv.DictReader(io.StringIO(csv_block)))

# ── plotting ──────────────────────────────────────────────────────────────────

def make_plot(name, slug, stakes, rows):
    fig, ax = plt.subplots()

    for i, stake in enumerate(stakes):
        col = f'net_worth{i + 1}'
        net_worths = [float(r[col]) for r in rows if r.get(col) not in (None, '')]
        ax.scatter(
            [stake] * len(net_worths),
            net_worths,
            s=3,
            marker=MARKERS[i],
            color=COLORS[i],
            label=f'P{i + 1}  (${stake:,})',
            alpha=0.5,
            linewidths=0,
        )

    ax.set_xlabel('Starting Stake ($)')
    ax.set_ylabel('Ending Net Worth ($)')
    ax.set_title(f'{name}  —  {N_GAMES} games, {len(stakes)} players')
    ax.legend(markerscale=4, fontsize='small')
    fig.tight_layout()

    out = f'plot_{slug}.png'
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f'  → saved {out}')

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    for name, slug, stakes in CONFIGS:
        print(f'{name} ...')
        rows = run_sim(stakes)
        print(f'  {len(rows)} games simulated')
        make_plot(name, slug, stakes, rows)
    print('Done.')
