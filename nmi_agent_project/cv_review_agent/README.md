# NMI Classification CV Agent

This agent audits the existing NMI forecastability classification with chart-based visual reasoning.

## Files

- `nmi_classification_cv_agent.py`: main agent script.
- `nmi_classification_cv_agent_api_key.txt`: paste the OpenAI API key here; this file is local-only and ignored.
- `outputs/NMI_classification_cv_review/plots/`: generated validation charts.
- `outputs/NMI_classification_cv_review/NMI_classification_cv_review.csv`: final audit table.
- `outputs/NMI_classification_cv_review/NMI_classification_cv_review.xlsx`: final audit table.

## Input

The script reads:

- `Datasets/LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv`
- `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary_threshold.csv`

The classification file must contain:

- `NMI`
- `forecastability_tier`

Useful diagnostic columns such as `zero_rate`, `longest_zero_run_hours`, `best_baseline_WAPE`, and component scores are passed to the model when present.

## Validation Images

For each NMI, the script generates two images:

1. Deep dive page from `MAST90106 Group 2 EDA v2.ipynb`:
   - Weekday vs weekend average profile
   - Yearly mean daily consumption
   - Average daily load shape by year
   - Monthly consumption by year

2. Additional quality page:
   - Active daily total with 30-day rolling mean
   - 30-day rolling standard deviation
   - Monthly zero-rate pattern
   - Consumption distribution with IQR outlier boundaries

## Output Columns

The final review table has exactly four columns:

- `NMI`
- `classified_tier`
- `cv_judgement`
- `cv_reason`

`cv_judgement` is one of:

- `reasonable`
- `questionable`
- `not_reasonable`

## Run

Install dependencies if needed:

```powershell
pip install -r nmi_agent_project\cv_review_agent\requirements.txt
```

Run a small test first:

```powershell
python nmi_agent_project\cv_review_agent\nmi_classification_cv_agent.py --limit 3
```

The default model is `gpt-5.4-mini`, with low-detail image input and concise output.

Use another model if needed:

```powershell
python nmi_agent_project\cv_review_agent\nmi_classification_cv_agent.py --limit 3 --model gpt-5.1
```

Run all NMIs:

```powershell
python nmi_agent_project\cv_review_agent\nmi_classification_cv_agent.py
```

Audit selected NMIs:

```powershell
python nmi_agent_project\cv_review_agent\nmi_classification_cv_agent.py --nmi 6102000812 --nmi VAAA000057
```
