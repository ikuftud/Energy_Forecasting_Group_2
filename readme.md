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

https://unimelbcloud-my.sharepoint.com/:f:/g/personal/apatupat_student_unimelb_edu_au/IgBnFz3XnapCTpnqk_MDdj4qAfIECybpomUPUaGjWRklgy0?e=dzGbCE

---

## 📊 Project Components

### 🔹 Literature Review

11 papers

**summary link**: https://www.overleaf.com/1495651168ybtnymnhncns#d7f736

**summary table**: https://unimelbcloud-my.sharepoint.com/:x:/r/personal/chiianc_student_unimelb_edu_au/_layouts/15/Doc.aspx?sourcedoc=%7BE38D8B67-F672-4F42-AEF0-C9B2745052D9%7D&file=literature_review_table.xlsx&fromShare=true&action=default&mobileredirect=true



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
