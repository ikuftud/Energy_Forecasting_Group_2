# Looking Forward: Forecasting Energy Consumption

## 📌 Overview
This project aims to analyse and forecast energy consumption across the University of Melbourne’s campus portfolio. The University operates over 450 buildings and consumes significant electricity and gas annually, making accurate forecasting essential for energy optimisation and sustainability planning.

The project focuses on using historical energy, weather, and billing data to understand consumption patterns and develop data-driven forecasting models to support operational and strategic decision-making.

---

## 📂 Project Structure

### Github

```
Energy_Forecasting_Group_2/
│
├── Datasets/                         # Raw datasets (stored locally, not tracked in GitHub)
│
├── scripts/                          # Python scripts (data processing, mapping)
│
├── EDA_Tasks/                        # Project EDA part
│
├── MAST90106 EDA.ipynb               
├── Project data exploration.ipynb    
│
├── project-brief-378.pdf             # Official project description
│
├── .gitignore                        # Ignore rules for large files and system files
└── README.md                         # Project documentation
```



### Data + Results 

**Onedrive Link**: https://unimelbcloud-my.sharepoint.com/:f:/g/personal/apatupat_student_unimelb_edu_au/IgBnFz3XnapCTpnqk_MDdj4qAfIECybpomUPUaGjWRklgy0?e=dzGbCE

---

## 📊 Project Components

### 🔹 Literature Review（11 papers）

**summary link**: https://www.overleaf.com/1495651168ybtnymnhncns#d7f736

**summary table**: https://unimelbcloud-my.sharepoint.com/:x:/r/personal/chiianc_student_unimelb_edu_au/Documents/literature_review_table.xlsx?d=we38d8b67f6724f42aef0c9b2745052d9&csf=1&web=1&e=k9Blqc

### 🔹 Shared Document

**report**: https://unimelbcloud-my.sharepoint.com/:w:/r/personal/chiianc_student_unimelb_edu_au/Documents/Outline%20for%20final%20week%20oral%20presentation.docx?d=wd03b572490814aee8b8b9d7935e68281&csf=1&web=1&e=nVlunm

**presentation Slides**: https://unimelbcloud-my.sharepoint.com/:p:/r/personal/chiianc_student_unimelb_edu_au/Documents/Semester%201%20project%20presentation%20slides.pptx?d=w3fc18f64bc9049359189bec90e46f820&csf=1&web=1&e=juRSJD

---

### 🔹 Exploratory Data Analysis (EDA)

- Understanding dataset structure and time index
- Checking missing values, zero values, and anomalies
- Analysing consumption patterns over time
- Identifying usable and reliable time series

---

## Python File Explanation

#### MAST90106 EDA.ipynb

* Removed 2020–2022 data and dropped 2 NMI columns (6102507141 and VAAA003225)
* Summary statistics computed
* For each NMI:
    * identified active window (first & last non-zero)
    * calculated zero count and zero %
* Created NMI summary table (sorted by zero %) and exported
* Plotted sample half-hourly time series
* Aggregated data to daily totals
* Plotted daily time series



#### Project data exploration.ipynb

- Half-hourly consumption time series (per NMI)
- Daily total consumption time series (per NMI)
- Multi-NMI comparison plots (subplots of different NMIs)
- Time series starting from first non-zero value (active period)
- Total consumption time series (sum across NMIs)


---

## Current Workspace Additions

This section documents additional files and outputs currently present in the project workspace. It is added as a supplement to the original README content above.

### Dataset Files

#### `Datasets/Clariti Consumption/`

- `LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv`
- `LMS_2013-01-01_2026-03-24_HALF_HOUR_au.pq`
- Main half-hourly electricity consumption dataset.
- Contains the timestamp column and one consumption column per NMI.

#### Building and NMI Mapping Files

- `Datasets/Archibus Extract_Buildings_May 2026.xlsx`
    - Building metadata, including building code, building name, building type, campus code, latitude, and longitude.
- `Datasets/LMS Serial to NMI Map.xlsx`
    - Links LMS location/meter information to NMI values.
- `Datasets/Parkville Substation Mapping.xlsx`
    - Shared/substation mapping between Parkville buildings and NMIs.
- `EDA_Tasks/4/building_nmi_mapping.json`
    - Additional manually curated NMI-building mapping information used by the NMI classification workflow.

#### Weather Files

- `Datasets/NMI to weather station.xlsx`
    - Maps NMIs to Bureau of Meteorology weather stations.
- `Datasets/weather station/`
    - Daily BoM weather station files used by the weather EDA notebook.
    - Each station contains `MaxTemp`, `MinTemp`, and `Rainfall` folders.
- `Datasets/weather/`
    - Earlier weather data folders for Olympic Park / Regional Office max temperature, min temperature, and rainfall.
- `Datasets/weather_host/weather_2025-10-06_2026-03-01_15min.csv`
    - Host-provided 15-minute weather dataset.

---

## EDA Notebooks in `EDA_Tasks/`

#### `MAST90106 Group 2 EDA.ipynb`

- Main group EDA notebook.
- Loads and checks the electricity consumption dataset.
- Calculates NMI-level active windows, zero-value behaviour, missing values, and basic diagnostics.
- Produces exploratory plots for NMI consumption behaviour.

#### `MAST90106 Group 2 EDA v2.ipynb`

- Extended EDA plotting notebook.
- Generates full time-series plots, deep-dive plots, rolling mean / rolling standard deviation plots, outlier plots, and lag-correlation analysis.
- Outputs many NMI-level visualisations to `EDA_Tasks/EDA Results/`.

#### `MAST90106 Group 2 EDA w Weather.ipynb`

- Weather visual EDA notebook.
- Reads `Datasets/NMI to weather station.xlsx` to map each NMI to a weather station.
- Reads daily BoM weather station data for maximum temperature, minimum temperature, and rainfall.
- Aggregates half-hourly NMI consumption to daily totals.
- Produces weather-station plots and NMI energy consumption with matched weather plots.
- Current generated output folder: `Datasets/EDA w Weather Results/`.

#### `MAST90106 Group 2 NMI score+classification.ipynb`

- NMI-level forecastability scoring and classification notebook.
- Calculates active window, data quality, recent coverage, temporal dependence, seasonality, stability, baseline backtesting error, and building mapping quality.
- Produces a weighted `forecastability_score`.
- Classifies NMIs into:
    - `Tier A - Strong forecasting candidate`
    - `Tier B - Usable with caution`
    - `Tier C - Short-history candidate`
    - `Tier D - Difficult forecasting candidate`
    - `Exclude / Needs Review`
- Outputs:
    - `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary.csv`
    - `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary.xlsx`
- Explanation document:
    - `EDA_Tasks/NMI_score_classification_explanation.md`

#### `MAST90106 Group 2 NMI plot.ipynb`

- Compact visual EDA notebook based on the NMI score/classification output.
- Produces overview plots for the full NMI population.
- Selects representative NMIs mathematically from each forecastability tier.
- Generates representative NMI diagnostic plots and priority tables.
- Outputs:
    - `EDA_Tasks/NMI_plot_results/overview_plots/`
    - `EDA_Tasks/NMI_plot_results/representative_nmi_plots/`
    - `EDA_Tasks/NMI_plot_results/priority_tables/`
- Explanation document:
    - `EDA_Tasks/NMI_plot_explanation.md`

#### `MAST90106 Group 2 Weather correlation analysis.ipynb`

- Weather-energy relationship analysis notebook.
- Intended to evaluate whether weather variables help explain electricity consumption, rather than only plotting weather data by itself.

#### Task Notebooks

- `EDA_Tasks/4/Task 4.ipynb`
    - NMI-building mapping related work.
- `EDA_Tasks/5/Task 5.ipynb`
    - Behaviour plot related work.
- `EDA_Tasks/6/Task 6.ipynb`
    - Structural-break / time-series change related work.
- `EDA_Tasks/8/Task 8.ipynb`
    - Daily and yearly stability analysis.
- `EDA_Tasks/9/Task 9.ipynb`
    - Lag-correlation analysis.
- `EDA_Tasks/10/Task 10.ipynb`
    - Distribution and outlier analysis.

---

## Generated Outputs

#### `EDA_Tasks/EDA Results/`

- Contains large batches of EDA plots generated by earlier EDA notebooks.
- Includes full time-series plots, deep-dive plots, rolling statistics plots, histogram/boxplot outputs, and zero-value pattern checks.

#### `EDA_Tasks/NMI_score_classification_results/`

- Contains the final NMI forecastability summary table in CSV and Excel formats.
- Each row represents one NMI and includes building metadata, diagnostic metrics, component scores, final classification, modelling recommendation, and reason text.

#### `EDA_Tasks/NMI_plot_results/`

- Contains compact visual EDA outputs:
    - overview plots;
    - representative NMI plots;
    - priority tables;
    - plot inventory files.

#### `Datasets/EDA w Weather Results/`

- Contains weather visual EDA output images.
- Current generated outputs include:
    - weather station min-max temperature plots;
    - weather station rainfall plots;
    - NMI daily energy consumption with matched weather plots.
