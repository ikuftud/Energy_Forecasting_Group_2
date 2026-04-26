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
├── Task/                             # Project EDA part
│
├── MAST90106 EDA.ipynb               
├── Project data exploration.ipynb    
│
├── project-brief-378.pdf             # Official project description
│
├── .gitignore                        # Ignore rules for large files and system files
└── README.md                         # Project documentation
```



### Data

https://unimelbcloud-my.sharepoint.com/:f:/g/personal/apatupat_student_unimelb_edu_au/IgBnFz3XnapCTpnqk_MDdj4qAfIECybpomUPUaGjWRklgy0?e=dzGbCE

---

## 📊 Project Components

### 🔹 Literature Review

11 papers

**summary link**: https://www.overleaf.com/read/dyxrymsdhymg#f0b61b

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

