#!/usr/bin/env python3
"""Deep-time (geological) global temperature: CENOGRID, last 67 million years."""
import numpy as np, pandas as pd
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt

OUT = "/tmp/datasets/plots"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
TMPC, WARM = "#1baf7a", "#eb6834"
mpl.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": SEC, "axes.edgecolor": BASE, "xtick.color": MUT, "ytick.color": MUT,
    "axes.titlecolor": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold", "figure.dpi": 130,
})

df = pd.read_excel("/tmp/datasets/CenoCO2/data/Westerhold.xlsx", "data")
df.columns = [c.strip() for c in df.columns]
df = df.rename(columns={"age_tuned": "age_Ma", "GMST (oC)": "gmst"}).sort_values("age_Ma")
df = df.dropna(subset=["age_Ma", "gmst"])
# smooth (rolling median over age-sorted points)
df["sm"] = df["gmst"].rolling(80, center=True, min_periods=20).median()

# save a tidy CSV too
df[["age_Ma", "benthic d18O VPDB CorrAdjusted", "gmst"]].rename(
    columns={"benthic d18O VPDB CorrAdjusted": "benthic_d18O_permil",
             "gmst": "global_mean_surface_temp_C"}
).to_csv(f"{OUT}/../deliver/temperature_cenozoic_CENOGRID_67Ma.csv", index=False)

fig, (axA, axB) = plt.subplots(2, 1, figsize=(12, 10))

# ---------- Panel A: full Cenozoic ----------
axA.plot(df.age_Ma, df.gmst, color=TMPC, lw=0.5, alpha=0.35)
axA.plot(df.age_Ma, df.sm, color=TMPC, lw=1.8)
axA.set_xlim(67, 0); axA.set_ylim(-8, 24)
axA.set_title("Global temperature over the last 67 million years (CENOGRID)")
axA.set_xlabel("Millions of years ago (Ma)")
axA.set_ylabel("Global mean surface T (°C, vs pre-industrial)")
axA.axhline(0, color=BASE, lw=1)
events = [
    (56.0, 12.5, "PETM"),
    (50.5, 14.5, "Early Eocene\nClimatic Optimum"),
    (34.0, 5.2, "Antarctic glaciation\n(Eocene–Oligocene)"),
    (15.8, 6.6, "Mid-Miocene\nOptimum"),
    (3.0, -1.0, "Onset of\nN. Hemisphere\nice ages"),
]
for a, y, lab in events:
    axA.annotate(lab, (a, y), xytext=(0, 16), textcoords="offset points",
                 ha="center", va="bottom", fontsize=8.5, color=SEC,
                 arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
axA.annotate("now", (0, df.gmst.iloc[0]), xytext=(10, 0), textcoords="offset points",
             color="#0f7d57", fontsize=9, fontweight="bold", va="center")
axA.text(0.99, 0.95, "Warmer than today for most of the era; a ~50-Myr cooling ends in the ice ages.",
         transform=axA.transAxes, ha="right", va="top", color=MUT, fontsize=8.5)

# ---------- Panel B: last 3 Myr zoom (ice-age cycles) ----------
z = df[df.age_Ma <= 3.0]
axB.plot(z.age_Ma, z.gmst, color=TMPC, lw=0.7, alpha=0.5)
axB.plot(z.age_Ma, z.sm, color=TMPC, lw=1.6)
axB.set_xlim(3.0, 0); axB.set_ylim(-8, 4)
axB.set_title("Zoom: the last 3 million years — the Pleistocene ice-age cycles")
axB.set_xlabel("Millions of years ago (Ma)")
axB.set_ylabel("Global mean surface T (°C)")
axB.axhline(0, color=BASE, lw=1)
axB.annotate("glacial–interglacial cycles\n(~100 kyr in the last ~1 Myr)",
             (1.4, -6.5), fontsize=8.5, color=SEC, ha="center")
axB.text(0.99, 0.06, "The 24,000-yr and instrumental records from the earlier plots live in the thin sliver at the far right.",
         transform=axB.transAxes, ha="right", va="bottom", color=MUT, fontsize=8.5)

for ax in (axA, axB):
    for s in ("left", "bottom"): ax.spines[s].set_color(BASE)
    ax.set_axisbelow(True)
fig.suptitle("Earth's temperature, deep-time — 67 Myr of the Cenozoic",
             fontsize=15, fontweight="bold", y=0.995)
fig.text(0.5, 0.005, "Data: Westerhold et al. 2020 CENOGRID (astronomically-tuned benthic δ18O), "
         "GMST via CenoCO2 calibration. Smoothed = rolling median.", ha="center", color=MUT, fontsize=8.5)
fig.tight_layout(rect=[0, 0.02, 1, 0.985])
fig.savefig(f"{OUT}/plot6_deeptime_cenozoic.png"); plt.close(fig)
print("peak warmth:", round(df.gmst.max(),1), "C at", round(df.loc[df.gmst.idxmax(),'age_Ma'],1), "Ma")
print("Saved plot6")
