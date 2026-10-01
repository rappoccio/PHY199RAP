#!/usr/bin/env python3
"""Bin all data by SOLAR CYCLE (13-month smoothed minima), % deviation vs the 1950 cycle (SC18)."""
import numpy as np, pandas as pd
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

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
PI_GMST = 13.9

# ---- solar-cycle boundaries: 13-month smoothed minima ----
m = pd.read_csv(f"{D}/sunspots_monthly_SILSO.txt", sep=r'[; ]+', engine='python', header=None,
                names=["year","month","date","ssn","sd","n"])
m = m[m.ssn >= 0].reset_index(drop=True)
sm = m.ssn.rolling(13, center=True, min_periods=7).mean()
peaks, _ = find_peaks(-sm.values, distance=96, prominence=15)
bnd = m.date.values[peaks]
cycles = [(bnd[i], bnd[i+1], i+1) for i in range(len(bnd)-1)]

def cyc_mean(date, val, a, b):
    s = (date >= a) & (date < b)
    return (np.nanmean(val[s]), int(s.sum())) if s.any() else (np.nan, 0)

# ---- datasets ----
co2 = pd.read_csv(f"{D}/co2_maunaloa_monthly_clean.csv"); co2 = co2[co2.co2_ppm_average > 0]
tl = pd.read_csv(f"{D}/temperature_timeline_McKay2022_XKCDstyle.csv")
ins = tl[tl.record == "AR6_instrumental_mean"].sort_values("x_value")
DAT = {
    "ssn": (m.date.values, m.ssn.values),
    "co2": (co2.decimal_date.values, co2.co2_ppm_deseasonalized.values),
    "tmp": (ins.x_value.values.astype(float), ins.temp_anomaly_C_vs_1850_1900.values),
}
tab = []
for a, b, sc in cycles:
    r = {"SC": sc, "start": a, "end": b, "mid": (a+b)/2}
    for k in DAT:
        r[k], r[k+"_n"] = cyc_mean(*DAT[k], a, b)
    tab.append(r)
tab = pd.DataFrame(tab)
tab.round(2).to_csv(f"{D}/solar_cycle_bins.csv", index=False)

# baseline cycle = closest-to-1950 cycle WITH data for each series
def baseline(col, min_n):
    have = tab[tab[col+"_n"] >= min_n]
    return have.iloc[(have["mid"] - 1950).abs().argmin()]
b_ssn = baseline("ssn", 60); b_co2 = baseline("co2", 36); b_tmp = baseline("tmp", 5)
tab["ssn_pct"] = 100*(tab.ssn - b_ssn.ssn)/b_ssn.ssn
tab["co2_pct"] = 100*(tab.co2 - b_co2.co2)/b_co2.co2
tK = b_tmp.tmp + PI_GMST + 273.15
tab["tmp_pct"] = 100*(tab.tmp - b_tmp.tmp)/tK

panels = [
    ("Sunspot number", SUNC, "ssn_pct", "ssn_n", 60,
     f"baseline SC{int(b_ssn.SC)} ({b_ssn.start:.0f}–{b_ssn.end:.0f}) = {b_ssn.ssn:.0f}"),
    ("Mauna Loa CO₂", CO2C, "co2_pct", "co2_n", 36,
     f"baseline SC{int(b_co2.SC)} ({b_co2.start:.0f}–{b_co2.end:.0f}, data from 1958) = {b_co2.co2:.0f} ppm"),
    ("Temperature (instr.)", TMPC, "tmp_pct", "tmp_n", 5,
     f"baseline SC{int(b_tmp.SC)} = {b_tmp.tmp:+.2f}°C anomaly (% vs absolute {tK:.0f} K)"),
]
fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
for ax, (name, c, col, ncol, minn, blab) in zip(axes, panels):
    d = tab[tab[ncol] >= minn]
    x = d["mid"].values; y = d[col].values; w = (d.end - d.start).values*0.8
    ax.axhline(0, color=BASE, lw=1.2)
    ax.bar(x, y, width=w, color=c, alpha=0.9, edgecolor=SURF, linewidth=1.2)
    for xi, yi, sc in zip(x, y, d.SC):
        ax.annotate(f"SC{int(sc)}", (xi, 0), xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8.5, fontweight="bold", color=INK, rotation=90)
    ax.set_title(f"{name} — % deviation per solar cycle vs the 1950 cycle   ({blab})", loc="left")
    ax.set_ylabel("% deviation")
    for s in ("left", "bottom"): ax.spines[s].set_color(BASE)
    ax.set_axisbelow(True)
axes[-1].set_xlabel("Solar cycle mid-year")
fig.suptitle("Binned by solar cycle (11-yr), as % deviation from the 1950-era cycle",
             fontsize=15, fontweight="bold", y=0.995)
fig.text(0.5, 0.006, "Cycle boundaries = 13-month-smoothed sunspot minima (turning points). "
         "Sunspots span all 24 cycles; CO₂ only since 1958; temperature since ~1850.",
         ha="center", color=MUT, fontsize=9)
fig.tight_layout(rect=[0, 0.02, 1, 0.985])
fig.savefig(f"{OUT}/plot9_solarcycle_bins_percent.png"); plt.close(fig)
print("baselines: ssn SC%d=%.1f | co2 SC%d=%.1f | tmp SC%d=%+.2f" %
      (b_ssn.SC,b_ssn.ssn,b_co2.SC,b_co2.co2,b_tmp.SC,b_tmp.tmp))
print("saved plot9 and solar_cycle_bins.csv")
