#!/usr/bin/env python3
"""New feature: ice-core CO2 (1010-2026). Millennium curve + re-run of the bin analyses."""
import numpy as np, pandas as pd
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

D, OUT = "/tmp/datasets/deliver", "/tmp/datasets/plots"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
CO2C, SUNC, TMPC, ICE = "#2a78d6", "#eb6834", "#1baf7a", "#6da7ec"
mpl.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": SEC, "axes.edgecolor": BASE, "xtick.color": MUT, "ytick.color": MUT,
    "axes.titlecolor": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130,
})
PI_GMST = 13.9
co2 = pd.read_csv(f"{D}/co2_combined_icecore_maunaloa.csv")
ice = co2[co2.source.str.startswith("ice")]; mlo = co2[co2.source.str.startswith("Mauna")]

# ============ PLOT 10: CO2 over the last millennium ============
fig, ax = plt.subplots(figsize=(12, 5.6))
ax.plot(ice.decimal_year, ice.ppm, color=ICE, lw=2.0, label="Ice cores (Law Dome)")
ax.plot(mlo.decimal_year, mlo.ppm, color=CO2C, lw=1.4, label="Mauna Loa (direct)")
ax.axhline(280, color=BASE, lw=1, ls=(0,(4,4)))
ax.annotate("pre-industrial ≈ 280 ppm", (1150, 280), xytext=(0, 6),
            textcoords="offset points", color=MUT, fontsize=9)
last = co2.iloc[-1]
ax.annotate(f"{last.ppm:.0f} ppm ({last.date[:4]})", (last.decimal_year, last.ppm),
            xytext=(-6, -4), textcoords="offset points", ha="right", color=CO2C, fontweight="bold")
ax.set_title("Atmospheric CO₂ over the last millennium — ice cores + Mauna Loa")
ax.set_xlabel("Year (CE)"); ax.set_ylabel("CO₂ concentration (ppm)")
ax.set_xlim(1000, 2040); ax.legend(frameon=False, loc="upper left")
ax.text(0.99, 0.05, "Flat near 280 ppm for ~800 yrs, then a near-vertical rise since ~1850. "
        "Source: 2 Degrees Institute (co2levels.org).", transform=ax.transAxes,
        ha="right", va="bottom", color=MUT, fontsize=8)
for s in ("left","bottom"): ax.spines[s].set_color(BASE)
fig.tight_layout(); fig.savefig(f"{OUT}/plot10_co2_millennium.png"); plt.close(fig)

# ============ solar-cycle boundaries (13-mo smoothed minima) ============
m = pd.read_csv(f"{D}/sunspots_monthly_SILSO.txt", sep=r'[; ]+', engine='python', header=None,
                names=["year","month","date","ssn","sd","n"]); m = m[m.ssn>=0].reset_index(drop=True)
sm = m.ssn.rolling(13,center=True,min_periods=7).mean()
peaks,_ = find_peaks(-sm.values, distance=96, prominence=15)
bnd = m.date.values[peaks]; cycles=[(bnd[i],bnd[i+1],i+1) for i in range(len(bnd)-1)]
def cyc_mean(date,val,a,b):
    s=(date>=a)&(date<b); return (np.nanmean(val[s]),int(s.sum())) if s.any() else (np.nan,0)

tmpdf = pd.read_csv(f"{D}/temperature_millennium_2degrees.csv")   # 1000 AD -> 2026, vs 1951-1980
TEMP_OFFSET = 14.0                                                 # 1951-1980 GMST (°C) for absolute K
DAT = {"ssn":(m.date.values,m.ssn.values),
       "co2":(co2.decimal_year.values,co2.ppm.values),
       "tmp":(tmpdf.decimal_year.values,tmpdf.anomaly_C.values)}
tab=[]
for a,b,sc in cycles:
    r={"SC":sc,"start":a,"end":b,"mid":(a+b)/2}
    for k in DAT: r[k],r[k+"_n"]=cyc_mean(*DAT[k],a,b)
    tab.append(r)
tab=pd.DataFrame(tab)
def base_at(col,minn):
    h=tab[tab[col+"_n"]>=minn]; return h.iloc[(h["mid"]-1850).abs().argmin()]
bS,bC,bT=base_at("ssn",60),base_at("co2",2),base_at("tmp",5)
tab["ssn_pct"]=100*(tab.ssn-bS.ssn)/bS.ssn
tab["co2_pct"]=100*(tab.co2-bC.co2)/bC.co2
tK=bT.tmp+TEMP_OFFSET+273.15; tab["tmp_pct"]=100*(tab.tmp-bT.tmp)/tK
tab.round(3).to_csv(f"{D}/solar_cycle_bins_icecoreCO2.csv",index=False)

# ============ PLOT 11: solar-cycle % deviation (CO2 now vs 1950 cycle) ============
panels=[("Sunspot number",SUNC,"ssn_pct","ssn_n",60,f"baseline SC{int(bS.SC)} ({bS.start:.0f}–{bS.end:.0f}) = {bS.ssn:.0f}"),
        ("CO₂ (ice core + Mauna Loa)",CO2C,"co2_pct","co2_n",1,f"baseline SC{int(bC.SC)} ({bC.start:.0f}–{bC.end:.0f}) = {bC.co2:.0f} ppm"),
        ("Temperature (2° Institute)",TMPC,"tmp_pct","tmp_n",2,f"baseline SC{int(bT.SC)} = {bT.tmp:+.2f}°C (vs abs {tK:.0f} K)")]
fig,axes=plt.subplots(3,1,figsize=(13,11),sharex=True)
for ax,(name,c,col,ncol,minn,blab) in zip(axes,panels):
    d=tab[tab[ncol]>=minn]; x=d["mid"].values; y=d[col].values; w=(d.end-d.start).values*0.8
    ax.axhline(0,color=BASE,lw=1.2); ax.bar(x,y,width=w,color=c,alpha=0.9,edgecolor=SURF,linewidth=1.2)
    for xi,sc in zip(x,d.SC):
        ax.annotate(f"SC{int(sc)}",(xi,0),xytext=(0,3),textcoords="offset points",
                    ha="center",va="bottom",fontsize=8.5,fontweight="bold",color=INK,rotation=90)
    ax.set_title(f"{name} — % deviation per solar cycle vs the ≈1850 cycle   ({blab})",loc="left",fontsize=10.5)
    ax.set_ylabel("% deviation")
    for s in ("left","bottom"): ax.spines[s].set_color(BASE)
    ax.set_axisbelow(True)
axes[-1].set_xlabel("Solar cycle mid-year")
fig.suptitle("Solar-cycle % deviation vs the ≈1850 (pre-industrial) cycle",fontsize=15,fontweight="bold",y=0.995)
fig.text(0.5,0.006,"Baseline = solar cycle nearest 1850 (pre-industrial). Ice-core CO₂ is decadally smoothed, "
         "so per-cycle means show trend, not 11-yr structure (CO₂ has none).",ha="center",color=MUT,fontsize=9)
fig.tight_layout(rect=[0,0.02,1,0.985]); fig.savefig(f"{OUT}/plot11_solarcycle_bins_percent_icecoreCO2.png"); plt.close(fig)

# ============ PLOT 12: 20-yr % bins, CO2 back to 1010 ============
def binned(years,values,edges,base_lo,base_hi):
    df=pd.DataFrame({"y":np.asarray(years,float),"v":np.asarray(values,float)})
    df["bin"]=pd.cut(df.y,edges,right=False,labels=edges[:-1]+10)
    g=df.groupby("bin",observed=False)["v"].agg(["mean","count"])
    base=df[(df.y>=base_lo)&(df.y<base_hi)]["v"].mean(); return g,base
E_long=np.arange(1010,2051,20); E_sun=np.arange(1690,2051,20)
sun_y=pd.read_csv(f"{D}/sunspots_yearly_SILSO.csv"); sun_y=sun_y[sun_y.sunspot_number>=0]
gC,bC2=binned(co2.decimal_year,co2.ppm,E_long,1840,1860)
gS,bS2=binned(sun_y.year_mid,sun_y.sunspot_number,E_sun,1840,1860)
gT,bT2=binned(tmpdf.decimal_year,tmpdf.anomaly_C,E_long,1840,1860)
tK2=bT2+TEMP_OFFSET+273.15
specs=[("CO₂ (ice core + Mauna Loa)",CO2C,gC,bC2,bC2,f"{bC2:.0f} ppm",(1000,2040)),
       ("Sunspot number",SUNC,gS,bS2,bS2,f"{bS2:.0f}",(1000,2040)),
       ("Temperature (2° Institute)",TMPC,gT,bT2,tK2,f"{tK2:.0f} K abs",(1000,2040))]
fig,axes=plt.subplots(3,1,figsize=(13,11))
for ax,(name,c,g,bmean,denom,blab,xlim) in zip(axes,specs):
    gg=g.dropna(subset=["mean"]); x=gg.index.astype(float).values
    pct=100*(gg["mean"].values-bmean)/denom
    ax.axhline(0,color=BASE,lw=1.2); ax.bar(x,pct,width=18,color=c,alpha=0.9,edgecolor=SURF,linewidth=1.0)
    ax.set_title(f"{name} — % deviation from 1840–1860 (baseline {blab})",loc="left",fontsize=10.5)
    ax.set_ylabel("% deviation"); ax.set_xlim(*xlim)
    for s in ("left","bottom"): ax.spines[s].set_color(BASE)
    ax.set_axisbelow(True)
axes[-1].set_xlabel("Bin center (year)")
fig.suptitle("20-yr bins, % deviation from the 1840–1860 (pre-industrial) baseline",fontsize=15,fontweight="bold",y=0.995)
fig.text(0.5,0.006,"Pre-industrial (1840–1860) baseline. Temperature shows the Medieval Warm Period and Little Ice Age; "
         "% is vs absolute kelvin.",ha="center",color=MUT,fontsize=9)
fig.tight_layout(rect=[0,0.02,1,0.985]); fig.savefig(f"{OUT}/plot12_20yr_bins_percent_icecoreCO2.png"); plt.close(fig)
print("CO2 baseline SC%d=%.1f ppm | 20yr 1840-60=%.1f ppm"%(bC.SC,bC.co2,bC2))
print("saved plot10, plot11, plot12")
