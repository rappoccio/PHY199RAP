#!/usr/bin/env python3
"""20-year binned deviation from the common recent (2001-2020) baseline."""
import numpy as np, pandas as pd
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt

D, OUT = "/tmp/datasets/deliver", "/tmp/datasets/plots"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
CO2C, SUNC, TMPC = "#2a78d6", "#eb6834", "#1baf7a"
mpl.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": SEC, "axes.edgecolor": BASE, "xtick.color": MUT, "ytick.color": MUT,
    "axes.titlecolor": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "figure.dpi": 130,
})
EDGES = np.arange(1690, 2051, 20)          # 20-yr bins aligned so [1950,1970) is a bin
CENTERS = EDGES[:-1] + 10
BASELINE = (1950, 1970)                     # baseline period

def binned(years, values):
    df = pd.DataFrame({"y": np.asarray(years, float), "v": np.asarray(values, float)})
    df["bin"] = pd.cut(df.y, EDGES, right=False, labels=CENTERS)
    g = df.groupby("bin", observed=False)["v"].agg(["mean", "count"])
    base = df[(df.y >= BASELINE[0]) & (df.y < BASELINE[1])]["v"].mean()
    g["dev"] = g["mean"] - base
    return g, base

# ---- load ----
co2 = pd.read_csv(f"{D}/co2_maunaloa_monthly_clean.csv")
co2 = co2[co2.co2_ppm_average > 0]
co2y = co2.groupby("year", as_index=False)["co2_ppm_deseasonalized"].mean()
sun = pd.read_csv(f"{D}/sunspots_yearly_SILSO.csv"); sun = sun[sun.sunspot_number >= 0]
tl = pd.read_csv(f"{D}/temperature_timeline_McKay2022_XKCDstyle.csv")
instr = tl[tl.record == "AR6_instrumental_mean"].sort_values("x_value")

series = [
    ("Mauna Loa CO₂",    CO2C, *binned(co2y.year, co2y.co2_ppm_deseasonalized), "ppm"),
    ("Sunspot number",   SUNC, *binned(sun.year_mid, sun.sunspot_number),        "count"),
    ("Temperature (instr.)", TMPC, *binned(instr.x_value, instr.temp_anomaly_C_vs_1850_1900), "°C"),
]

fig, axes = plt.subplots(3, 1, figsize=(11, 11), sharex=True)
for ax, (name, c, g, base, unit) in zip(axes, series):
    gg = g.dropna(subset=["mean"])
    x = gg.index.astype(float).values
    dev = gg["dev"].values
    ax.axhline(0, color=BASE, lw=1.2)
    ax.bar(x, dev, width=18, color=c, alpha=0.9, edgecolor=SURF, linewidth=1.5)
    ax.set_title(f"{name} — 20-yr bin mean minus 1950–1970 average"
                 f"   (baseline = {base:.1f} {unit})", loc="left")
    ax.set_ylabel(f"Deviation ({unit})")
    for xi, d in zip(x, dev):                      # value labels
        ax.annotate(f"{d:+.0f}" if unit == "count" else f"{d:+.1f}",
                    (xi, d), xytext=(0, 4 if d >= 0 else -12), textcoords="offset points",
                    ha="center", fontsize=8, color=SEC)
    for s in ("left", "bottom"): ax.spines[s].set_color(BASE)
    ax.set_axisbelow(True)
axes[-1].set_xlabel("Bin center (year)")
axes[-1].set_xlim(EDGES[0]-5, EDGES[-1]+5)
fig.suptitle("20-year bins as deviation from the 1950–1970 baseline",
             fontsize=15, fontweight="bold", y=0.995)
fig.text(0.5, 0.005, "Each bar = mean over a 20-yr block minus that series' 1950–1970 mean. "
         "Sunspot 11-yr cycle is averaged out. Temperature = instrumental (IPCC AR6).",
         ha="center", color=MUT, fontsize=9)
fig.tight_layout(rect=[0, 0.02, 1, 0.985])
fig.savefig(f"{OUT}/plot5_20yr_bins_deviation.png"); plt.close(fig)

# print tables
for name, c, g, base, unit in series:
    print(f"\n{name}  (baseline 2001-2020 = {base:.2f} {unit})")
    t = g.dropna(subset=['mean']).copy()
    print(t.assign(mean=t['mean'].round(2), dev=t['dev'].round(2))[['mean','count','dev']].to_string())
print("\nSaved plot5")
