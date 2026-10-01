#!/usr/bin/env python3
"""
1-D distribution plots of ending net worth.
One figure per configuration, all players on one axis, open step histograms.

  dist_equal.png       — overflow bin for net worth > $20,000
  dist_oligarchy.png   — explicit bankruptcy bin at $0
  dist_company_town.png — explicit bankruptcy bin at $0
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

# ── config ────────────────────────────────────────────────────────────────────
CONFIGS = [
    # (title, slug, stakes, overflow_at, show_bankruptcy_bin)
    ("Equal Stakes",     "equal",        [1500, 1500, 1500, 1500, 1500, 1500], 20_000, False),
    ("Oligarchy Stakes", "oligarchy",    [  10,   10,   10,  100,  100,  8770], None,   True),
    ("Company Town",     "company_town", [   1,    1,    1,    1,    1,  8995], None,   True),
]

N_GAMES = 1000
JOBS    = 8
SEED    = 0
N_BINS  = 60

COLORS   = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
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

# ── plotting ──────────────────────────────────────────────────────────────────

def make_dist_plot(name, slug, stakes, rows, overflow=None, bankruptcy_bin=False):
    fig, ax = plt.subplots()
    n = len(stakes)

    # Collect per-player arrays
    player_vals = []
    for i in range(n):
        col = f'net_worth{i + 1}'
        vals = np.array([float(r[col]) for r in rows
                         if r.get(col) not in (None, '')])
        player_vals.append(vals)

    all_vals = np.concatenate(player_vals)
    xmax = overflow if overflow is not None else float(all_vals.max())

    # Build bins
    bin_width = xmax / N_BINS
    if bankruptcy_bin:
        # First bin is [0, bin_width) — collects bankrupt players ($0)
        # plus a tiny bit of the non-zero tail, but for Oligarchy/Company Town
        # this bin is overwhelmingly bankruptcies.
        bins = np.concatenate([[0], np.linspace(bin_width, xmax + bin_width, N_BINS)])
    else:
        bins = np.linspace(0, xmax + bin_width, N_BINS + 1)

    overflow_bin_mid = (bins[-2] + bins[-1]) / 2  # midpoint of last bin

    for i, (stake, vals) in enumerate(zip(stakes, player_vals)):
        if overflow is not None:
            # Clip values above overflow into the last overflow bin
            vals_plot = np.where(vals > overflow, overflow_bin_mid, vals)
        else:
            vals_plot = vals

        ax.hist(vals_plot, bins=bins, histtype='step',
                color=COLORS[i], linewidth=1.2, linestyle=LINESTYLES[i],
                label=f'P{i + 1}  (${stake:,})')

    # ── overflow marker ──────────────────────────────────────────────────────
    if overflow is not None:
        ax.axvline(overflow, color='gray', ls='--', lw=0.9, alpha=0.7)
        # Custom x-ticks: replace tick nearest to overflow with '>$20k'
        ax.figure.canvas.draw()          # force tick computation
        raw_ticks = [t for t in ax.get_xticks()
                     if 0 <= t <= bins[-1]]
        labels = []
        for t in raw_ticks:
            if abs(t - overflow) < bin_width * 0.6:
                labels.append(f'>${overflow // 1000}k')
            else:
                labels.append(f'${t:,.0f}')
        ax.set_xticks(raw_ticks)
        ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)

    # ── bankruptcy bin label ─────────────────────────────────────────────────
    if bankruptcy_bin:
        ax.annotate('← bankrupt\n   ($0)',
                    xy=(bin_width * 0.5, 0), xycoords=('data', 'axes fraction'),
                    xytext=(bin_width * 4, 0.6), textcoords=('data', 'axes fraction'),
                    fontsize=7.5, color='#555555',
                    arrowprops=dict(arrowstyle='->', color='#888888', lw=0.8))

    # ── formatting ───────────────────────────────────────────────────────────
    if overflow is None:
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
        plt.xticks(rotation=30, ha='right', fontsize=8)

    ax.set_xlabel('Ending Net Worth ($)')
    ax.set_ylabel('Games')
    ax.set_title(f'{name}  —  {N_GAMES} games, {n} players')
    ax.legend(fontsize='small')
    fig.tight_layout()

    out = f'dist_{slug}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  → saved {out}')

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    for name, slug, stakes, overflow, bkpt in CONFIGS:
        print(f'{name} ...')
        rows = run_sim(stakes)
        print(f'  {len(rows)} rows')
        make_dist_plot(name, slug, stakes, rows,
                       overflow=overflow, bankruptcy_bin=bkpt)
    print('Done.')
