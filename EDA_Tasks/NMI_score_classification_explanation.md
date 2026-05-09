# NMI Forecastability Score and Classification Explanation

This document explains the current version of:

`EDA_Tasks/MAST90106 Group 2 NMI score+classification.ipynb`

It describes the notebook logic, the scoring and classification method, the meaning of the exported results, and the definition of every column in the final output table.

Related outputs:

- CSV output: `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary.csv`
- Excel output: `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary.xlsx`

## 1. Purpose of the Notebook

The NMI electricity consumption dataset has inconsistent time coverage. Some NMIs have long histories, while others only have recent records. Using one fixed training window for all NMIs would make the comparison unfair, especially for short-history NMIs.

This notebook avoids visual or subjective judgement. Instead, it calculates reproducible diagnostic metrics for each NMI and combines them into a `forecastability_score`. The score is then used to classify NMIs into groups such as strong forecasting candidates, usable with caution, short-history candidates, difficult candidates, and NMIs that need review.

## 2. Current Notebook Inputs and Outputs

The current notebook uses fixed project paths under:

`/Users/chenlinchao/Desktop/Energy_Forecasting_Group_2`

Main input files:

| Input | Purpose |
|---|---|
| `Datasets/Clariti Consumption/LMS_2013-01-01_2026-03-24_HALF_HOUR_au.pq` | Main half-hourly electricity consumption table. |
| `Datasets/Archibus Extract_Buildings_May 2026.xlsx` | Building metadata, including building type. |
| `Datasets/LMS Serial to NMI Map.xlsx` | NMI, meter serial, and location/building code mapping. |
| `Datasets/Parkville Substation Mapping.xlsx` | Shared/substation building mapping information. |
| `EDA_Tasks/4/building_nmi_mapping.json` | Optional manually curated NMI-building mapping file, used only if it exists. |

The notebook defines a CSV path for the energy data, but the current version reads the parquet file directly.

Output folder:

`EDA_Tasks/NMI_score_classification_results/`

The notebook exports the same final table in two formats:

- `NMI_forecastability_summary.csv`
- `NMI_forecastability_summary.xlsx`

The CSV and Excel files contain the same rows and columns. CSV is better for code-based analysis, while Excel is easier for manual inspection.

## 3. Overall Workflow

The notebook follows this workflow:

1. Import libraries and set fixed project paths.
2. Load half-hourly electricity data from the parquet file.
3. Standardise NMI column names by removing the `" consumption"` suffix.
4. Remove two NMIs already excluded in earlier EDA: `6102507141` and `VAAA003225`.
5. Load building metadata and clean unreliable `building_type` values.
6. Build the NMI-to-building mapping table from the available mapping sources.
7. Summarise building information into one row per NMI.
8. Calculate diagnostic metrics for each NMI within its own active window.
9. Run simple baseline backtesting.
10. Convert raw metrics into 0-1 percentile scores.
11. Calculate the weighted `forecastability_score`.
12. Assign `forecastability_tier`.
13. Generate modelling recommendations and automatic reason text.
14. Export the final table to CSV and Excel.

## 4. Active Window Definition

The notebook does not force all NMIs to share the same start date.

For each NMI:

- `active_start` is the timestamp of the first non-zero reading.
- `active_end` is the timestamp of the last non-zero reading.
- All main diagnostic metrics are calculated within this active window.

This design allows long-history and short-history NMIs to be evaluated using their own available operating periods.

## 5. Building Mapping and Building Type Logic

The notebook builds NMI-building metadata using several sources:

1. `Archibus Extract_Buildings_May 2026.xlsx`
2. `LMS Serial to NMI Map.xlsx`
3. `Parkville Substation Mapping.xlsx`
4. Optional `EDA_Tasks/4/building_nmi_mapping.json`

The Archibus `Building Type` field is cleaned before use. Values such as `.N/A`, `N/A`, empty strings, `c`, and values that start with a digit are treated as unreliable and converted to missing values. Missing building type values are later shown as `Unknown`.

The final table includes:

- building code or codes;
- building name or names;
- building type;
- building type group;
- campus code or codes;
- mapping source;
- mapping quality.

`building_type_group` is defined as:

| Value | Meaning |
|---|---|
| `Single` | The NMI maps to one distinct building type. |
| `Mixed` | The NMI maps to more than one distinct building type. |
| `Unknown` | Building type information is missing or unavailable. |

`mapping_quality` is derived from mapping sources and the number of linked buildings. Possible labels include:

| Mapping quality | Meaning |
|---|---|
| `one_building_mapped` | The NMI maps clearly to one building. |
| `many_to_one` | Multiple NMIs or mapping entries point to one building relationship. |
| `multi_building_mapped` | The NMI maps to more than one building. |
| `substation_shared_multi_building` | The NMI appears in shared/substation mapping and maps to multiple buildings. |
| `many_to_many` | The mapping suggests a many-to-many relationship. |
| `unmapped` | The NMI is explicitly listed as unmapped. |
| `unknown` | The mapping is missing or cannot be classified. |

## 6. Baseline Forecast Performance Design

The notebook uses three simple baselines:

| Baseline | Meaning |
|---|---|
| `lag48` | Uses the same half-hour reading from yesterday as the prediction. There are 48 half-hourly readings per day. |
| `lag336` | Uses the same half-hour reading from last week as the prediction. There are 336 half-hourly readings per week. |
| `calendar` | Uses the expanding historical average for the same weekday and half-hour. |

The validation period is defined separately for each NMI:

- If the active history is shorter than 365 days, baseline backtesting is not performed.
- If the active history is long enough, the first 365 days of the active window are treated as the minimum history period.
- The validation period starts from `active_start + 365 days`.
- If the validation period has fewer than `48 * 30` half-hourly points, no valid baseline WAPE is returned.

The error metric is WAPE:

```text
WAPE = sum(abs(actual - prediction)) / sum(abs(actual))
```

Lower WAPE means the NMI can be predicted more accurately by simple baselines. This improves `performance_score`.

## 7. Diagnostic Metrics

The notebook calculates metrics in five broad groups.

| Group | Metrics |
|---|---|
| Active history and coverage | `active_start`, `active_end`, `active_years`, `active_readings`, `recent_coverage_12m`, `recent_coverage_24m` |
| Data quality | `missing_rate`, `zero_rate`, `negative_count`, `longest_zero_run`, `longest_zero_run_hours`, `longest_zero_run_ratio`, `outlier_rate` |
| Temporal dependence and seasonality | `lag_1_corr`, `lag_2_corr`, `lag_48_corr`, `lag_336_corr`, `daily_cycle_strength`, `weekly_pattern_strength`, `seasonality_strength` |
| Stability | `trend_strength`, `yearly_variation`, `structural_break_score` |
| Backtesting | `validation_start`, `validation_points`, `validation_months`, `WAPE_lag48`, `WAPE_lag336`, `WAPE_calendar`, `best_baseline_type`, `best_baseline_WAPE` |

## 8. Score Components

All component scores are scaled between 0 and 1 using percentile-based scoring. A value closer to 1 is better for forecasting.

| Component score | Weight | Interpretation |
|---|---:|---|
| `performance_score` | 35% | Lower `best_baseline_WAPE` gives a higher score. |
| `data_quality_score` | 20% | Lower missing rate, zero rate, long zero-run ratio, and outlier rate give a higher score. |
| `history_score` | 15% | Longer active history, better recent coverage, and more validation months give a higher score. |
| `temporal_pattern_score` | 15% | Stronger lag correlations, daily cycle, weekly pattern, and seasonality give a higher score. |
| `stability_score` | 10% | Lower trend strength, yearly variation, and structural break score give a higher score. |
| `mapping_score` | 5% | Clearer NMI-to-building mapping gives a higher score. |

The overall score is:

```text
forecastability_score =
0.35 * performance_score
+ 0.20 * data_quality_score
+ 0.15 * history_score
+ 0.15 * temporal_pattern_score
+ 0.10 * stability_score
+ 0.05 * mapping_score
```

If a component is missing, the notebook automatically re-normalises the available weights when calculating `forecastability_score`.

`score_confidence` records how much of the original component weight was available for that NMI. The maximum is 1.

## 9. Classification Rules

The classification is performed in three stages.

First, NMIs that are clearly unsuitable for direct forecasting are assigned to:

`Exclude / Needs Review`

This happens when any of the following is true:

- `status` is `Dead` or `Mostly inactive`;
- `active_years < 0.25`;
- `zero_rate >= 0.80`.

Second, short-history NMIs are assigned to:

`Tier C - Short-history candidate`

This happens when any of the following is true and the NMI has not already been excluded:

- `active_years < 1.0`;
- `validation_months < 3`;
- `best_baseline_WAPE` is missing.

Tier C does not mean the data is poor. It means the NMI does not have enough history for the same individual-model evaluation used for long-history NMIs.

Third, all remaining eligible NMIs are classified using score quantiles:

| Rule | Tier |
|---|---|
| `forecastability_score >= 75th percentile` among eligible NMIs | `Tier A - Strong forecasting candidate` |
| `forecastability_score <= 25th percentile` among eligible NMIs | `Tier D - Difficult forecasting candidate` |
| Remaining eligible NMIs | `Tier B - Usable with caution` |

## 10. Modelling Recommendations

The notebook generates a recommended modelling strategy for each tier.

| Tier | Recommended strategy |
|---|---|
| `Tier A - Strong forecasting candidate` | Individual model; suitable for regular forecasting and benchmark model comparison. |
| `Tier B - Usable with caution` | Individual model with caution; consider recent-window training, changepoint features, and anomaly handling. |
| `Tier C - Short-history candidate` | Pooled/global model; borrow strength from similar NMIs/building types and calendar/weather features. |
| `Tier D - Difficult forecasting candidate` | Low priority for individual model; consider aggregation or operational/data-quality review. |
| `Exclude / Needs Review` | Exclude from individual forecasting until mapping/data quality is reviewed. |

The `reason` column is generated automatically using diagnostic conditions such as:

- short or long active history;
- low or high baseline WAPE;
- high or very low zero rate;
- long zero runs;
- strong or weak daily/weekly temporal dependency;
- large rolling-mean shift;
- mixed building types;
- mapping quality requiring review.

## 11. Current Result Summary

The current exported summary table contains 99 NMIs and 52 columns.

Forecastability tier counts:

| Tier | Count |
|---|---:|
| `Tier B - Usable with caution` | 45 |
| `Tier A - Strong forecasting candidate` | 23 |
| `Tier D - Difficult forecasting candidate` | 23 |
| `Tier C - Short-history candidate` | 5 |
| `Exclude / Needs Review` | 3 |

The CSV and Excel files are generated from the same `final_table`. Excel may display values such as `0.0` as `0`, or show timestamps with Excel date formatting. These are format differences, not calculation differences.

## 12. Column Dictionary

| Column | Type | Meaning |
|---|---|---|
| `NMI` | ID | National Meter Identifier. This is the primary key of the output table, with one row per NMI. |
| `building_codes` | Building metadata | Building code or codes mapped to this NMI. Multiple values are separated by semicolons. |
| `building_names` | Building metadata | Building name or names mapped to this NMI. Multiple values are separated by semicolons. |
| `building_type` | Building metadata | Building type from Archibus. Multiple types are separated by semicolons; missing or unreliable values are shown as `Unknown`. |
| `building_type_group` | Building metadata | `Single`, `Mixed`, or `Unknown`, based on how many distinct building types are mapped to the NMI. |
| `building_type_count` | Building metadata | Number of distinct building types linked to the NMI. |
| `campus_codes` | Building metadata | Campus code or codes linked to the NMI. Multiple values are separated by semicolons. |
| `mapping_quality` | Building metadata | Quality label for the NMI-to-building mapping. |
| `mapping_sources` | Building metadata | Source files or rules used for the NMI-to-building mapping. |
| `active_start` | Active window | Timestamp of the first non-zero reading for the NMI. |
| `active_end` | Active window | Timestamp of the last non-zero reading for the NMI. |
| `active_years` | Active window | Number of years between `active_start` and `active_end`. |
| `active_readings` | Active window | Number of half-hourly readings inside the active window. |
| `status` | Usability | Zero-rate-based status: `Active`, `Mostly Active`, `Intermittent`, `Mostly inactive`, or `Dead`. |
| `recent_coverage_12m` | Coverage | Proportion of non-zero readings in the most recent 12 months of the full dataset. |
| `recent_coverage_24m` | Coverage | Proportion of non-zero readings in the most recent 24 months of the full dataset. |
| `missing_rate` | Data quality | Proportion of missing values within the active window. |
| `zero_rate` | Data quality | Proportion of zero values within the active window. Missing values are treated as zero for this calculation. |
| `negative_count` | Data quality | Number of negative readings within the active window. |
| `longest_zero_run` | Data quality | Longest consecutive run of zero readings within the active window, measured in half-hourly points. |
| `longest_zero_run_hours` | Data quality | Longest consecutive zero run converted into hours, equal to `longest_zero_run * 0.5`. |
| `longest_zero_run_ratio` | Data quality | Longest zero run divided by the total active-window length. |
| `outlier_rate` | Data quality | Proportion of readings identified as outliers using the IQR rule. |
| `lag_1_corr` | Temporal dependence | Correlation between the current reading and the previous half-hour reading. |
| `lag_2_corr` | Temporal dependence | Correlation between the current reading and the reading from two half-hours earlier. |
| `lag_48_corr` | Temporal dependence | Correlation between the current reading and the same half-hour yesterday. |
| `lag_336_corr` | Temporal dependence | Correlation between the current reading and the same half-hour last week. |
| `daily_cycle_strength` | Seasonality | Variance of half-hour-of-day group means divided by total variance. Higher values indicate stronger daily patterns. |
| `weekly_pattern_strength` | Seasonality | Variance of weekday plus half-hour group means divided by total variance. Higher values indicate stronger weekly patterns. |
| `seasonality_strength` | Seasonality | Variance of monthly mean daily totals divided by variance of daily totals. Higher values indicate stronger monthly seasonality. |
| `trend_strength` | Stability | Absolute linear trend slope of daily totals divided by average daily total. Higher values indicate stronger long-term trend change. |
| `yearly_variation` | Stability | Standard deviation of yearly mean daily totals divided by their mean. Higher values indicate larger year-to-year variation. |
| `structural_break_score` | Stability | Maximum absolute change in the 30-day rolling mean divided by average daily total. Higher values indicate stronger structural shifts. |
| `validation_start` | Backtesting | Start timestamp of the baseline validation period, usually `active_start + 365 days`. |
| `validation_points` | Backtesting | Number of half-hourly observations available in the validation period. |
| `validation_months` | Backtesting | Number of distinct calendar months covered by the validation period. |
| `WAPE_lag48` | Backtesting | WAPE of the `lag48` baseline. Lower is better. |
| `WAPE_lag336` | Backtesting | WAPE of the `lag336` baseline. Lower is better. |
| `WAPE_calendar` | Backtesting | WAPE of the `calendar` baseline. Lower is better. |
| `best_baseline_type` | Backtesting | Baseline with the lowest WAPE among `lag48`, `lag336`, and `calendar`. |
| `best_baseline_WAPE` | Backtesting | WAPE of the best baseline. This is used to calculate `performance_score`. |
| `performance_score` | Score | Percentile score derived from `best_baseline_WAPE`. Lower WAPE gives a higher score. |
| `data_quality_score` | Score | Combined score from `missing_rate`, `zero_rate`, `longest_zero_run_ratio`, and `outlier_rate`. |
| `history_score` | Score | Combined score from `active_years`, `recent_coverage_24m`, and `validation_months`. |
| `temporal_pattern_score` | Score | Combined score from `lag_48_corr`, `lag_336_corr`, `daily_cycle_strength`, `weekly_pattern_strength`, and `seasonality_strength`. |
| `stability_score` | Score | Combined score from `trend_strength`, `yearly_variation`, and `structural_break_score`. More stable NMIs receive higher scores. |
| `mapping_score` | Score | Score derived from `mapping_quality`. Clearer mapping receives a higher score. |
| `forecastability_score` | Score | Weighted overall score from the six component scores. This is the main numeric basis for tier classification after special-case rules. |
| `score_confidence` | Score | Total available component weight for the NMI. The maximum is 1; lower values mean the score is based on fewer available components. |
| `forecastability_tier` | Classification | Final forecastability/difficulty classification. |
| `recommended_model_strategy` | Recommendation | Automatically generated modelling recommendation based on the tier. |
| `reason` | Explanation | Automatically generated explanation for the tier and score profile. |

## 13. Suggested Report Wording

The method can be described as:

> Because different NMIs have different active history lengths and operating periods, we do not force a single common training window. Instead, we identify each NMI's active window and construct a reproducible forecastability score using data quality, history coverage, temporal dependence, structural stability, mapping clarity, and simple baseline backtesting error.

Useful report outputs include:

- the number of NMIs in each tier;
- the distribution of `forecastability_score`;
- the relationship between `forecastability_tier` and `building_type_group`;
- representative NMIs from each tier;
- an explanation that Tier C means short history, not necessarily poor data quality.
