# PHY199RAP — Project State (checkpoint 2026-08-19)

Frozen baseline of the climate-data work. Everything below is stable; new work
(e.g. ice-core CO₂) is added as a *new feature* on top of this.

## datasets/
| file | what it is | span |
|---|---|---|
| `sunspots_yearly_SILSO.csv` | SILSO v2 yearly mean sunspot number | 1700–2024 |
| `sunspots_monthly_SILSO.txt` | SILSO v2 monthly mean sunspot number (used for cycle minima) | 1749–2021 |
| `co2_maunaloa_monthly_NOAA_official.csv` | NOAA GML Mauna Loa monthly CO₂ (verbatim) | 1958–2026 |
| `co2_maunaloa_monthly_clean.csv` | same, tidy columns | 1958–2026 |
| `temperature_timeline_McKay2022_XKCDstyle.csv` | Osman/Kaufman/AR6 temperature records, vs 1850–1900 | 24 kyr–2020 |
| `temperature_marcott2013_global_holocene.csv` | Marcott global Holocene stack | 0–11.3 kyr BP |
| `temperature_GISP2_greenland_alley2000.csv` | GISP2 Greenland ice-core temp | 0–49 kyr BP |
| `temperature_cenozoic_CENOGRID_67Ma.csv` | Westerhold 2020 CENOGRID GMST | 0–67 Myr |
| `solar_cycle_bins.csv` | per-solar-cycle means of every dataset | SC1–SC24 |
| `REFERENCES.md` | full citations for all sources | — |

## plots/  (each has a matching make_*.py script)
| file | content |
|---|---|
| `plot1_keeling_curve.png` | Mauna Loa CO₂ 1958–2026 |
| `plot2_sunspots.png` | Sunspot number + 11-yr cycle |
| `plot3_temperature_timeline.png` | 24-kyr paleo + instrumental temperature |
| `plot4_rates_grid.png` | value / derivative / %-per-yr for all three |
| `plot5_20yr_bins_deviation.png` | 20-yr bins, absolute deviation vs 1950–1970 |
| `plot6_deeptime_cenozoic.png` | 67-Myr Cenozoic temperature |
| `plot7_master_timeline.png` | single log-time temperature axis, 67 Myr → today |
| `plot8_20yr_bins_percent.png` | 20-yr bins, % deviation vs 1950–1970 |
| `plot9_solarcycle_bins_percent.png` | solar-cycle bins, % deviation vs 1950 cycle |

## New feature in progress
- Ice-core CO₂ (2 Degrees Institute: Law Dome 1010–1955 + Mauna Loa 1958+),
  `co2_combined_icecore_maunaloa.csv` — supersedes the Mauna Loa-only CO₂ and gives
  CO₂ a real 1950 baseline. Analyses re-run on this appear as `plot10+`.
