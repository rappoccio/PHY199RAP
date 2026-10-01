#!/usr/bin/env python3
"""
Sweep P1-P5 stakes from 1500 down to 1 (P6 gets the rest).
Plot P1's ending net-worth distribution for each scenario on one axis.
"""

import subprocess
import csv
import io
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── scenarios ─────────────────────────────────────────────────────────────────
TOTAL     = 9_000          # 6 players × $1,500 standard pot
P15_STEPS = [1500, 1000, 500, 250, 100, 1]

SCENARIOS = []
for s in P15_STEPS:
    p6 = TOTAL - 5 * s
    stakes = [s] * 5 + [p6]
    SCENARIOS.append((s, p6, stakes))

N_GAMES  = 1000
JOBS     = 8
SEED     = 0
N_BINS   = 60
OVERFLOW = 20_000

COLORS     = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
LINESTYLES = ['-', '--', ':', '-.', (0,(3,1,1,1)), (0,(5,1))]

# ── simulation ────────────────────────────────────────────────────────────────

def run_sim(stakes):
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
    csv_block = result.stdout.split('\n\n')[0]
    return list(csv.DictReader(io.StringIO(csv_block)))

# ── plot ──────────────────────────────────────────────────────────────────────

def make_sweep_plot(scenarios_data):
    fig, ax = plt.subplots()

    bin_width = OVERFLOW / N_BINS
    # First bin [0, bin_width) captures bankruptcies; then N_BINS regular bins
    bins = np.concatenate([[0], np.linspace(bin_width, OVERFLOW + bin_width, N_BINS)])

    for idx, (p15_stake, p6_stake, vals) in enumerate(scenarios_data):
        vals = np.array(vals)
        # Clip values above OVERFLOW into overflow bin midpoint
        overflow_mid = OVERFLOW + bin_width / 2
        vals_plot = np.where(vals > OVERFLOW, overflow_mid, vals)

        ax.hist(vals_plot, bins=bins, histtype='step',
                color=COLORS[idx], linewidth=1.3,
                linestyle=LINESTYLES[idx],
                label=f'P1-5 = ${p15_stake:,}  /  P6 = ${p6_stake:,}')

    # Overflow marker
    ax.axvline(OVERFLOW, color='gray', ls='--', lw=0.9, alpha=0.7)
    ax.figure.canvas.draw()
    raw_ticks = [t for t in ax.get_xticks() if 0 <= t <= bins[-1]]
    labels = [f'>${OVERFLOW // 1000}k' if abs(t - OVERFLOW) < bin_width * 0.6
              else f'${t:,.0f}' for t in raw_ticks]
    ax.set_xticks(raw_ticks)
    ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)

    # Bankruptcy annotation on first bin
    ax.annotate('← bankrupt\n   ($0)',
                xy=(bin_width * 0.5, 0), xycoords=('data', 'axes fraction'),
                xytext=(bin_width * 5, 0.55), textcoords=('data', 'axes fraction'),
                fontsize=7.5, color='#555555',
                arrowprops=dict(arrowstyle='->', color='#888888', lw=0.8))

    ax.set_yscale('log')
    ax.set_xlabel('Player 1 Ending Net Worth ($)')
    ax.set_ylabel('Games')
    ax.set_title(f'Player 1 outcomes as stake advantage shifts to P6\n'
                 f'{N_GAMES} games per scenario')
    ax.legend(fontsize='small', title='Stakes', title_fontsize='small')
    fig.tight_layout()

    out = 'dist_p1_sweep.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  → saved {out}')

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    scenarios_data = []
    for p15_stake, p6_stake, stakes in SCENARIOS:
        print(f'P1-5 = ${p15_stake:,}, P6 = ${p6_stake:,} ...')
        rows = run_sim(stakes)
        p1_vals = [float(r['net_worth1']) for r in rows
                   if r.get('net_worth1') not in (None, '')]
        print(f'  {len(p1_vals)} values')
        scenarios_data.append((p15_stake, p6_stake, p1_vals))

    print('Plotting ...')
    make_sweep_plot(scenarios_data)
    print('Done.')
