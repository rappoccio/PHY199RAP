#!/usr/bin/env python3
"""20-year binned data as PERCENT deviation from the 1950-1970 baseline."""
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
EDGES = np.arange(1690, 2051, 20)
CENTERS = EDGES[:-1] + 10
BASELINE = (1950, 1970)

def binned(years, values):
    df = pd.DataFrame({"y": np.asarray(years, float), "v": np.asarray(values, float)})
    df["bin"] = pd.cut(df.y, EDGES, right=False, labels=CENTERS)
    g = df.groupby("bin", observed=False)["v"].agg(["mean", "count"])
    base = df[(df.y >= BASELINE[0]) & (df.y < BASELINE[1])]["v"].mean()
    return g, base

co2 = pd.read_csv(f"{D}/co2_maunaloa_monthly_clean.csv"); co2 = co2[co2.co2_ppm_average > 0]
co2y = co2.groupby("year", as_index=False)["co2_ppm_deseasonalized"].mean()
sun = pd.read_csv(f"{D}/sunspots_yearly_SILSO.csv"); sun = sun[sun.sunspot_number >= 0]
tl = pd.read_csv(f"{D}/temperature_timeline_McKay2022_XKCDstyle.csv")
instr = tl[tl.record == "AR6_instrumental_mean"].sort_values("x_value")

gc, bc = binned(co2y.year, co2y.co2_ppm_deseasonalized)
gs, bs = binned(sun.year_mid, sun.sunspot_number)
gt, bt = binned(instr.x_value, instr.temp_anomaly_C_vs_1850_1900)

# percent denominators: CO2 & sunspots on native value; temperature on ABSOLUTE Kelvin
PI_GMST = 13.9                        # 1850-1900 global mean surface T (°C)
bt_abs_K = bt + PI_GMST + 273.15      # absolute K of the 1950-1970 baseline
series = [
    ("Mauna Loa CO₂",        CO2C, gc, bc,       f"{bc:.1f} ppm"),
    ("Sunspot number",       SUNC, gs, bs,       f"{bs:.1f}"),
    ("Temperature (instr.)", TMPC, gt, bt_abs_K, f"{bt_abs_K:.1f} K abs (anomaly {bt:+.2f}°C)"),
]

fig, axes = plt.subplots(3, 1, figsize=(11, 11), sharex=True)
for ax, (name, c, g, denom, blab) in zip(axes, series):
    gg = g.dropna(subset=["mean"])
    x = gg.index.astype(float).values
    base_mean = {"Mauna Loa CO₂": bc, "Sunspot number": bs, "Temperature (instr.)": bt}[name]
    pct = 100 * (gg["mean"].values - base_mean) / denom
    ax.axhline(0, color=BASE, lw=1.2)
    ax.bar(x, pct, width=18, color=c, alpha=0.9, edgecolor=SURF, linewidth=1.5)
    ax.set_title(f"{name} — % deviation from 1950–1970   (baseline {blab})", loc="left")
    ax.set_ylabel("% deviation / baseline")
    for xi, p in zip(x, pct):
        ax.annotate(f"{p:+.2f}%" if abs(p) < 1 else f"{p:+.0f}%",
                    (xi, p), xytext=(0, 4 if p >= 0 else -12), textcoords="offset points",
                    ha="center", fontsize=8, color=SEC)
    for s in ("left", "bottom"): ax.spines[s].set_color(BASE)
    ax.set_axisbelow(True)
axes[-1].set_xlabel("Bin center (year)")
axes[-1].set_xlim(EDGES[0]-5, EDGES[-1]+5)
fig.suptitle("20-year bins as PERCENT deviation from the 1950–1970 baseline",
             fontsize=15, fontweight="bold", y=0.995)
fig.text(0.5, 0.006, "CO₂ & sunspot %: relative to native baseline value.  Temperature %: relative to absolute T in "
         "kelvin (anomaly crosses zero), so numbers are tiny.",
         ha="center", color=MUT, fontsize=8.5)
fig.tight_layout(rect=[0, 0.02, 1, 0.985])
fig.savefig(f"{OUT}/plot8_20yr_bins_percent.png"); plt.close(fig)

for name, c, g, denom, blab in series:
    base_mean = {"Mauna Loa CO₂": bc, "Sunspot number": bs, "Temperature (instr.)": bt}[name]
    gg = g.dropna(subset=["mean"])
    print(f"\n{name} (denom {blab})")
    print((100*(gg['mean']-base_mean)/denom).round(2).to_string())
print("\nSaved plot8")
