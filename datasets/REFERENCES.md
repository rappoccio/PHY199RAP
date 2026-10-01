# Dataset References — PHY199RAP

Three topics, downloaded/compiled Aug 2026. Files are CSV, ready for plotting and calculation.

---

## 1. Sunspot number — `sunspots_yearly_SILSO.csv`

Yearly mean total sunspot number, **1700–2024** (325 rows). Version 2.0 series.

- Columns: `year_mid` (mid-year, e.g. 1700.5), `sunspot_number`, `std_dev`, `n_observations`, `definitive_flag`. Missing values = `-1`.
- **Source:** SILSO (Sunspot Index and Long-term Solar Observations), Royal Observatory of Belgium, Brussels. File `SN_y_tot_V2.0.csv`.
- **URL:** https://www.sidc.be/SILSO/datafiles — direct: https://www.sidc.be/SILSO/DATA/SN_y_tot_V2.0.csv
- **Cite:** SILSO, World Data Center — Sunspot Number and Long-term Solar Observations, Royal Observatory of Belgium, on-line Sunspot Number catalogue.
- **Currency note:** this copy ends at 2024. SILSO also publishes monthly (since 1749) and daily (since 1818) series updated to the current month; the yearly value for a given calendar year is finalized after that year ends.

## 2. Atmospheric CO₂ concentration (Mauna Loa) — `co2_maunaloa_monthly_NOAA_official.csv` and `co2_maunaloa_monthly_clean.csv`

Monthly mean CO₂ in parts per million (ppm), **March 1958 – July 2026**. The "official" file is the verbatim NOAA download (with its header/metadata); the "clean" file keeps `year, month, decimal_date, co2_ppm_average, co2_ppm_deseasonalized` for direct use.

- **Source:** NOAA Global Monitoring Laboratory (GML), Mauna Loa Observatory. File `co2_mm_mlo.csv`. 1958–1974 values are from C.D. Keeling / Scripps (SIO); later values are NOAA GML.
- **URL:** https://gml.noaa.gov/ccgg/trends/data.html — direct: https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv
- **Cite:** Lan, X., Tans, P. and K.W. Thoning: Trends in globally-averaged CO₂ determined from NOAA GML measurements; and C.D. Keeling et al., Scripps Institution of Oceanography.
- Note: Mauna Loa measurements were suspended after the Nov 2022 eruption; Dec 2022–Jul 2023 come from a nearby Maunakea site. This is the most up-to-date of the three topics (through mid-2026).

*(Also included as a bonus: `co2_emissions_global_OWID_GCP.csv` — global CO₂ **emissions** 1750–2024, Mt CO₂/yr by source, from the Global Carbon Project via Our World in Data — https://github.com/owid/co2-data. This is emissions, not concentration; keep it separate from the Mauna Loa concentration data above.)*

## 3. Earth's temperature timeline — three files

### `temperature_timeline_McKay2022_XKCDstyle.csv`  ← recommended
The modern, self-consistent version of the XKCD "Earth Temperature Timeline," all anomalies baselined to **1850–1900**. Long ("tidy") format: `record, x_kind, x_value, temp_anomaly_C_vs_1850_1900, lower_5pct, upper_95pct`. `x_kind` is either `age_BP` (years before present) or `year_CE`.

Records included and how they map onto the XKCD sources you named:

| record | span | role / XKCD counterpart |
|---|---|---|
| `Osman_LGMR_dataassim` | 100–23,900 BP | Last Glacial Maximum → present; **modern successor to Shakun 2012 and to Annan & Hargreaves 2013** (LGM ≈ −7 °C) |
| `Kaufman_Temp12k` | 0–12,000 BP | Holocene; **modern successor to Marcott 2013** |
| `AR6_instrumental_mean` | 1850–2020 | Instrumental record; **IPCC AR6** four-dataset mean |
| `AR6_SSP1-2.6 / SSP2-4.5 / SSP3-7.0` | 1850–2300 | Future projections; **IPCC AR6** |
| `Hansen_benthic_stack`, `Snyder_SST_stack` | to ~160,000+ BP | deep-time context (bonus) |

- **Source:** McKay, N.P. (2022), "Past and future warming — comparison figure," Zenodo. https://doi.org/10.5281/zenodo.5842209 · repo: https://github.com/nickmckay/past-and-future-warming-comparison-figure
- **Underlying data:** Osman et al. (2021) *Nature* 599:239–244 (https://doi.org/10.1038/s41586-021-03984-4); Kaufman et al. (2020) Temp12k, *Scientific Data* 7:201; IPCC AR6 WG1 (2021); Hansen et al. (2013); Snyder (2016).

### `temperature_marcott2013_global_holocene.csv`
The **original XKCD Holocene source**: Marcott's global temperature stack (Standard 5×5 grid), **0–11,300 years BP** (565 rows). Columns: `age_yr_BP, global_temp_anomaly_C, uncertainty_1sigma_C`.
- **Cite:** Marcott, S.A., Shakun, J.D., Clark, P.U., Mix, A.C. (2013), "A Reconstruction of Regional and Global Temperature for the Past 11,300 Years," *Science* 339:1198–1201. https://doi.org/10.1126/science.1228026
- Extracted from the paper's Database S1 (mirrored in EarthSystemDiagnostics/climproxyrecords).

### `temperature_GISP2_greenland_alley2000.csv`  (bonus)
Central-Greenland (GISP2) ice-core temperature, **~95 yr BP to 49,000 yr BP** (1,632 rows) — a *regional* record, not global, but it covers your original "last 40,000 years" span in one series. Columns: `age_kyr_BP, temperature_C` (absolute °C at the summit).
- **Cite:** Alley, R.B. (2000), "The Younger Dryas cold interval as viewed from central Greenland," *Quaternary Science Reviews* 19:213–226. Data: NOAA/WDS Paleoclimatology, contribution 2004-013.

---

### On "updates to 2026"
- **CO₂ (Mauna Loa):** yes — updated monthly; this copy runs through **July 2026**.
- **Sunspots:** updated monthly/daily by SILSO; the yearly file here ends 2024 (2025's yearly mean finalizes after year-end).
- **Paleo temperature (Shakun, Marcott, Alley, Annan & Hargreaves):** these are *published historical reconstructions* and do not get revised annually. What has "updated" since XKCD (2016) is the science itself — newer reconstructions (Kaufman Temp12k 2020, Osman 2021) and the newer IPCC assessment (AR6 2021), all captured in the McKay timeline file above.

### A note on how these were fetched
This sandbox blocks direct downloads from `sidc.be`, `gml.noaa.gov`, and `ncei.noaa.gov`. The SILSO and paleo files were obtained from faithful GitHub mirrors of the identical source files; the Mauna Loa CO₂ file was provided directly by you (NOAA GML, created 2026-08-05).
