#!/usr/bin/env python3
"""PHY199RAP: Mauna Loa CO2, sunspots, and temperature — plots + rate analysis."""
import numpy as np, pandas as pd
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import SymmetricalLogLocator

D = "/tmp/datasets/deliver"
OUT = "/tmp/datasets/plots"

# ---- palette (validated dataviz defaults) ----
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
CO2C, SUNC, TMPC = "#2a78d6", "#eb6834", "#1baf7a"   # blue / orange / aqua

mpl.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 11,
    "text.color": INK, "axes.labelcolor": SEC, "axes.edgecolor": BASE,
    "xtick.color": MUT, "ytick.color": MUT, "axes.titlecolor": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold", "figure.dpi": 130,
})

def style(ax):
    ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("left", "bottom"): ax.spines[s].set_color(BASE)

# ============================================================ load data
co2 = pd.read_csv(f"{D}/co2_maunaloa_monthly_clean.csv")
co2 = co2[co2["co2_ppm_average"] > 0].copy()          # drop any sentinels
sun = pd.read_csv(f"{D}/sunspots_yearly_SILSO.csv")
sun = sun[sun["sunspot_number"] >= 0].copy()
tl  = pd.read_csv(f"{D}/temperature_timeline_McKay2022_XKCDstyle.csv")

osman = tl[tl.record == "Osman_LGMR_dataassim"].copy()
kauf  = tl[tl.record == "Kaufman_Temp12k"].copy()
instr = tl[tl.record == "AR6_instrumental_mean"].sort_values("x_value").copy()
# age_BP -> calendar year (BP referenced to 1950)
osman["year"] = 1950 - osman["x_value"];  osman = osman.sort_values("year")
kauf["year"]  = 1950 - kauf["x_value"];    kauf  = kauf.sort_values("year")

# ============================================================ PLOT 1: Keeling
fig, ax = plt.subplots(figsize=(9, 5.2))
ax.plot(co2["decimal_date"], co2["co2_ppm_average"], color=CO2C, lw=0.9,
        alpha=0.55, label="Monthly average")
ax.plot(co2["decimal_date"], co2["co2_ppm_deseasonalized"], color=CO2C, lw=2.2,
        label="Seasonally adjusted trend")
ax.set_title("The Keeling Curve — Atmospheric CO₂ at Mauna Loa")
ax.set_xlabel("Year"); ax.set_ylabel("CO₂ concentration (ppm)")
ax.legend(frameon=False, loc="upper left")
last = co2.iloc[-1]
ax.annotate(f"{last.co2_ppm_average:.1f} ppm\n({int(last.year)}-{int(last.month):02d})",
            (last.decimal_date, last.co2_ppm_average), xytext=(-8, -34),
            textcoords="offset points", color=CO2C, fontsize=10, ha="right", fontweight="bold")
ax.text(0.99, 0.02, "Source: NOAA GML (Keeling/Scripps + NOAA). Seasonal wiggle = NH growing season.",
        transform=ax.transAxes, ha="right", va="bottom", color=MUT, fontsize=8)
style(ax); fig.tight_layout(); fig.savefig(f"{OUT}/plot1_keeling_curve.png"); plt.close(fig)

# ============================================================ PLOT 2: Sunspots
fig, ax = plt.subplots(figsize=(11, 4.8))
ax.fill_between(sun["year_mid"], sun["sunspot_number"], color=SUNC, alpha=0.18, lw=0)
ax.plot(sun["year_mid"], sun["sunspot_number"], color=SUNC, lw=1.3)
sm = sun["sunspot_number"].rolling(11, center=True, min_periods=6).mean()
ax.plot(sun["year_mid"], sm, color="#b8420f", lw=2.0, label="11-yr running mean")
ax.set_title("Sunspot Number, 1700–2024 — the ~11-year Solar Cycle")
ax.set_xlabel("Year"); ax.set_ylabel("Yearly mean sunspot number")
ax.set_xlim(1700, 2026); ax.set_ylim(0, None)
ax.legend(frameon=False, loc="upper left")
ax.text(0.99, 0.95, "Source: SILSO v2.0 (Royal Observatory of Belgium)",
        transform=ax.transAxes, ha="right", va="top", color=MUT, fontsize=8)
style(ax); fig.tight_layout(); fig.savefig(f"{OUT}/plot2_sunspots.png"); plt.close(fig)

# ============================================================ PLOT 3: timeline
fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 5.2),
                               gridspec_kw={"width_ratios": [2.6, 1]}, sharey=True)
# left: paleo, x = kyr before present, reversed so time flows to the right
axL.plot(osman["x_value"]/1000, osman["temp_anomaly_C_vs_1850_1900"], color=TMPC, lw=2.2,
         label="Osman 2021 (data assimilation)")
axL.fill_between(osman["x_value"]/1000, osman["lower_5pct"], osman["upper_95pct"],
                 color=TMPC, alpha=0.15, lw=0)
axL.plot(kauf["x_value"]/1000, kauf["temp_anomaly_C_vs_1850_1900"], color="#7a5c00", lw=1.6,
         label="Kaufman 2020 (Temp12k, Holocene)")
axL.set_xlim(24, 0)
axL.set_title("Global temperature, last 24,000 years")
axL.set_xlabel("Thousands of years before present"); axL.set_ylabel("Temperature anomaly (°C vs 1850–1900)")
axL.axhline(0, color=BASE, lw=1)
axL.legend(frameon=False, loc="lower right", fontsize=9)
axL.annotate("Last Glacial Maximum", (osman["x_value"].iloc[0]/1000+ -0, osman["temp_anomaly_C_vs_1850_1900"].iloc[0]),
             xytext=(6, 14), textcoords="offset points", color=SEC, fontsize=9)
# right: instrumental
axR.plot(instr["x_value"], instr["temp_anomaly_C_vs_1850_1900"], color=TMPC, lw=2.4)
axR.fill_between(instr["x_value"], instr["lower_5pct"], instr["upper_95pct"], color=TMPC, alpha=0.15, lw=0)
axR.set_xlim(1850, 2020); axR.axhline(0, color=BASE, lw=1)
axR.set_title("Instrumental (IPCC AR6)"); axR.set_xlabel("Year")
il = instr.iloc[-1]
axR.annotate(f"+{il.temp_anomaly_C_vs_1850_1900:.2f}°C\n({int(il.x_value)})",
             (il.x_value, il.temp_anomaly_C_vs_1850_1900), xytext=(-6, -6),
             textcoords="offset points", ha="right", color="#0f7d57", fontweight="bold", fontsize=10)
for a in (axL, axR): style(a)
fig.suptitle("A Timeline of Earth's Temperature (updated science; no projections)",
             fontsize=14, fontweight="bold", y=1.01)
fig.tight_layout(); fig.savefig(f"{OUT}/plot3_temperature_timeline.png", bbox_inches="tight"); plt.close(fig)

# ============================================================ PLOT 4: rate grid
def deriv(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    return np.gradient(y, x)

# --- CO2: annual means of deseasonalized trend ---
co2y = co2.groupby("year", as_index=False)["co2_ppm_deseasonalized"].mean()
co2y = co2y[(co2y.year >= 1959) & (co2y.year <= 2025)]   # full years only
cy, cv = co2y.year.values, co2y.co2_ppm_deseasonalized.values
cd = deriv(cy, cv);  cpct = 100*cd/cv

# --- Sunspots ---
sy, sv = sun.year_mid.values, sun.sunspot_number.values
sd = deriv(sy, sv)
sd_sm = pd.Series(sd).rolling(11, center=True, min_periods=6).mean().values
s_thr = 0.01*np.nanmax(sv)               # 1% of max; below this, %/yr excluded
spct = 100*sd/sv
spct = np.where(sv < s_thr, np.nan, spct)

# --- Temperature: instrumental, absolute Kelvin for % ---
ty, tv = instr.x_value.values.astype(float), instr.temp_anomaly_C_vs_1850_1900.values
BASE_K = 13.9 + 273.15                    # 1850-1900 GMST ~13.9 C
tK = tv + BASE_K
td = deriv(ty, tv)
td_sm = pd.Series(td).rolling(15, center=True, min_periods=6).mean().values
tpct = 100*td/tK

cols = [
    ("Mauna Loa CO₂", CO2C, cy, cv, cd, cpct, "ppm", "ppm/yr", None, None),
    ("Sunspot number",    SUNC, sy, sv, sd, spct, "count", "count/yr", sd_sm, None),
    ("Temperature (instr.)", TMPC, ty, tv, td, tpct, "°C anomaly", "°C/yr", td_sm, tK),
]
fig, axes = plt.subplots(3, 3, figsize=(14.5, 10.5))
rows = ["Value", "Rate of change (absolute / yr)", "Rate of change (% / yr)"]
for j, (name, c, x, v, d, pct, vu, du, dsm, _k) in enumerate(cols):
    a0, a1, a2 = axes[0, j], axes[1, j], axes[2, j]
    # row 0 value
    a0.plot(x, v, color=c, lw=1.8); a0.set_title(name)
    a0.set_ylabel(f"Value ({vu})" if j == 0 else vu)
    # row 1 abs derivative
    a1.axhline(0, color=BASE, lw=1)
    a1.plot(x, d, color=c, lw=1.0, alpha=0.5 if dsm is not None else 1.0)
    if dsm is not None:
        a1.plot(x, dsm, color=c, lw=2.2)
    a1.set_ylabel(f"d/dt ({du})" if j == 0 else du)
    # row 2 percent
    a2.axhline(0, color=BASE, lw=1)
    a2.plot(x, pct, color=c, lw=1.2)
    a2.set_ylabel("% change / yr")
    a2.set_xlabel("Year")
    for a in (a0, a1, a2): style(a)
# per-column caveat notes
axes[2, 1].text(0.5, 0.97, "%/yr excluded where sunspot number\n< 1% of record maximum (removes 1/0 blow-ups)",
                transform=axes[2,1].transAxes, ha="center", va="top", color=MUT, fontsize=8)
axes[2, 2].text(0.5, 0.07, "% computed on absolute scale (T+273.15 K,\n1850–1900 baseline ≈13.9°C)",
                transform=axes[2,2].transAxes, ha="center", va="bottom", color=MUT, fontsize=8)
axes[0, 2].text(0.5, 0.07, "Instrumental only: paleo records are too\nsmoothed for per-year rates",
                transform=axes[0,2].transAxes, ha="center", va="bottom", color=MUT, fontsize=8)
# rows labels on the left
for i, r in enumerate(rows):
    axes[i, 0].annotate(r, xy=(-0.32, 0.5), xycoords="axes fraction", rotation=90,
                        ha="center", va="center", color=SEC, fontweight="bold", fontsize=11)
fig.suptitle("Rate of change: value, absolute derivative, and percent-per-year",
             fontsize=15, fontweight="bold", y=1.00)
fig.tight_layout(); fig.savefig(f"{OUT}/plot4_rates_grid.png", bbox_inches="tight"); plt.close(fig)

# summary numbers
print("CO2 latest rate  :", round(cd[-1],2), "ppm/yr  |", round(cpct[-1],3), "%/yr  @", int(cy[-1]))
print("Temp latest rate :", round(td[-1],4), "C/yr   |", round(tpct[-1],4), "%/yr  @", int(ty[-1]))
print("Sunspot |d| max  :", round(np.nanmax(np.abs(sd)),1), "count/yr")
print("Saved 4 figures to", OUT)
