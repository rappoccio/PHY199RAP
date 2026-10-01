#!/usr/bin/env python3
"""XKCD-style single-axis temperature timeline: 67 Myr -> today on a log-time axis."""
import numpy as np, pandas as pd
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter

D, OUT = "/tmp/datasets/deliver", "/tmp/datasets/plots"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
C_DEEP, C_DEGLAC, C_INSTR = "#4a3aa7", "#1baf7a", "#eb6834"   # violet / aqua / orange
mpl.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": SEC, "axes.edgecolor": BASE, "xtick.color": MUT, "ytick.color": MUT,
    "axes.titlecolor": INK, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130,
})
NOW = 2025

# ---- deep time (CENOGRID) ----
ceno = pd.read_csv(f"{D}/temperature_cenozoic_CENOGRID_67Ma.csv").sort_values("age_Ma")
ceno["ya"] = ceno["age_Ma"]*1e6
ceno["sm"] = ceno["global_mean_surface_temp_C"].rolling(80, center=True, min_periods=20).median()
deep = ceno[ceno["ya"] >= 25000]

# ---- deglaciation + Holocene (Osman) and instrumental (AR6) ----
tl = pd.read_csv(f"{D}/temperature_timeline_McKay2022_XKCDstyle.csv")
os_ = tl[tl.record == "Osman_LGMR_dataassim"].copy().sort_values("x_value")
os_["ya"] = os_["x_value"] + (NOW-1950)
osman = os_[(os_["ya"] >= 175) & (os_["ya"] < 25000)]
ins = tl[tl.record == "AR6_instrumental_mean"].copy().sort_values("x_value")
ins["ya"] = NOW - ins["x_value"]
ins = ins[ins["ya"] >= 3]

fig, ax = plt.subplots(figsize=(14, 6.6))
ax.set_xscale("log")
ax.plot(deep["ya"], deep["sm"], color=C_DEEP, lw=1.8, label="Deep time — CENOGRID (Westerhold 2020)")
ax.plot(osman["ya"], osman["temp_anomaly_C_vs_1850_1900"], color=C_DEGLAC, lw=2.2,
        label="Last 24 kyr — Osman 2021")
ax.plot(ins["ya"], ins["temp_anomaly_C_vs_1850_1900"], color=C_INSTR, lw=2.6,
        label="Instrumental — IPCC AR6")
ax.axhline(0, color=BASE, lw=1)

ax.set_xlim(1.2e8, 3)                          # deep past left, present right
ax.set_ylim(-8, 16)
ticks = [1e8,1e7,1e6,1e5,1e4,1e3,1e2,1e1]
labs = ["100 Myr","10 Myr","1 Myr","100 kyr","10 kyr","1 kyr","100 yr","10 yr"]
ax.xaxis.set_major_locator(FixedLocator(ticks)); ax.xaxis.set_major_formatter(FixedFormatter(labs))
ax.grid(True, which="major", axis="both", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.set_xlabel("Time before present (log scale)")
ax.set_ylabel("Global temperature (°C vs 1850–1900 ≈ pre-industrial)")
ax.set_title("A Timeline of Earth's Temperature — 67 million years to today, on one axis",
             fontsize=14, fontweight="bold")

# event annotations (x = years ago, y)
ann = [
    (5.6e7, 12.8, "PETM", C_DEEP),
    (5.0e7, 14.5, "Eocene hothouse", C_DEEP),
    (3.4e7, 4.4, "Antarctica\nglaciates", C_DEEP),
    (1.6e7, 6.6, "Mid-Miocene\nOptimum", C_DEEP),
    (1.0e6, -3.2, "Ice ages\nbegin", C_DEEP),
    (2.1e4, -6.9, "Last Glacial\nMaximum", C_DEGLAC),
    (7e3, 0.9, "Holocene", C_DEGLAC),
]
for x, y, t, c in ann:
    ax.annotate(t, (x, y), xytext=(0, 12), textcoords="offset points", ha="center",
                fontsize=8.5, color=SEC, arrowprops=dict(arrowstyle="-", color=MUT, lw=0.7))
il = ins.iloc[-1]
ax.annotate(f"you are here\n+{il.temp_anomaly_C_vs_1850_1900:.2f}°C ({int(il.x_value)})",
            (il["ya"], il.temp_anomaly_C_vs_1850_1900), xytext=(-8, 34), textcoords="offset points",
            ha="right", fontsize=9, color=C_INSTR, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=C_INSTR, lw=1.2))
ax.legend(frameon=False, loc="lower left", fontsize=9.5)
ax.text(0.5, -0.16, "Log time axis: each gridline is 10x older to the left. Reconstructions differ slightly where they meet "
        "(different proxies/methods); deep-time resolution is coarse.",
        transform=ax.transAxes, ha="center", color=MUT, fontsize=8.5)
for s in ("left", "bottom"): ax.spines[s].set_color(BASE)
fig.tight_layout()
fig.savefig(f"{OUT}/plot7_master_timeline.png", bbox_inches="tight"); plt.close(fig)
print("Saved plot7")
