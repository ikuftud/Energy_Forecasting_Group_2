# NMI Forecastability Score Design

This note explains how the main component scores in `EDA_Tasks/nmi_score_classification_threshold.py` are calculated and used:

```text
performance_score
data_quality_score
history_score
temporal_pattern_score
stability_score
mapping_score
```

Every score is scaled between 0 and 1. A value closer to 1 means the NMI is stronger on that dimension and more suitable for forecasting. A value closer to 0 means higher risk or higher forecasting difficulty.

## Overall Flow

The script first calculates raw diagnostic metrics for each NMI, such as baseline WAPE, missing rate, zero rate, active history, temporal pattern strength, stability, and building-mapping quality.

It then converts those raw metrics into six component scores:

```text
performance_score       Baseline forecasting performance
data_quality_score      Data cleanliness and continuity
history_score           Length and recency of usable history
temporal_pattern_score  Strength of learnable time patterns
stability_score         Stability of the load pattern
mapping_score           Reliability of the NMI-to-building mapping
```

The final score is:

```text
forecastability_score
```

The default weights are:

```text
performance_score       35%
data_quality_score      20%
history_score           15%
temporal_pattern_score  15%
stability_score         10%
mapping_score            5%
```

If one component is missing, for example when an NMI does not have enough history for WAPE backtesting, the script re-normalises the weights across the available components. The final score does not become missing just because one component is unavailable.

## General Scoring Rules

The script uses two scoring styles.

### Fixed-Threshold Scoring

Fixed thresholds are used for data-quality metrics. The rule is direct: the metric falls into a range, and that range maps to a score.

Example:

```text
missing_rate <= 0.001 -> 1.00
missing_rate <= 0.010 -> 0.90
...
```

### Percentile Scoring

Most `history_score`, `temporal_pattern_score`, and `stability_score` sub-scores use percentile scoring.

For metrics where higher is better:

```text
score = percentile rank among all valid NMIs
```

For metrics where lower is better:

```text
score = 1 - percentile rank + 1 / number of valid NMIs
```

So:

```text
best-ranked NMI -> score close to 1
worst-ranked NMI -> score close to 0
all valid values identical -> score = 0.5
missing value -> score remains missing
```

Percentile scoring is not a fixed business threshold. It is a relative ranking rule.

## performance_score

`performance_score` measures whether simple baseline methods can already forecast this NMI reasonably well.

The script tests three baselines:

```text
lag48      Same half-hour yesterday
lag336     Same half-hour last week
calendar   Historical average for the same weekday and half-hour
```

Each baseline is evaluated with WAPE:

```text
Lower WAPE means better forecasting performance.
```

The script keeps the best baseline error:

```text
best_baseline_WAPE
```

It then converts WAPE into `performance_score` using min-max scaling:

```text
performance_score = 1 - (best_baseline_WAPE - min_WAPE) / (max_WAPE - min_WAPE)
```

Meaning:

```text
lowest WAPE -> performance_score = 1
highest WAPE -> performance_score = 0
if all valid WAPE values are identical -> performance_score = 0.5
if WAPE is missing -> performance_score is missing
```

Design rationale: if an NMI can already be forecast well by simple lag or calendar baselines, its load pattern is likely clear and repeatable enough for more advanced forecasting models.

## data_quality_score

`data_quality_score` measures whether the raw readings are clean, continuous, and reliable.

It is the average of four sub-scores:

```text
data_quality_score = mean(missing_score, zero_score, zero_run_score, outlier_score)
```

Missing sub-scores are skipped.

### missing_score

This comes from `missing_rate`.

Lower missing rate gives a higher score. The fixed-threshold rule is:

```text
missing_rate <= 0.001 -> 1.00
missing_rate <= 0.010 -> 0.90
missing_rate <= 0.050 -> 0.75
missing_rate <= 0.100 -> 0.50
missing_rate <= 0.200 -> 0.25
missing_rate >  0.200 -> 0.05
missing_rate missing   -> missing
```

### zero_score

This comes from `zero_rate`.

Lower zero rate gives a higher score. The fixed-threshold rule is:

```text
zero_rate <= 0.010 -> 1.00
zero_rate <= 0.050 -> 0.90
zero_rate <= 0.100 -> 0.75
zero_rate <= 0.300 -> 0.50
zero_rate <= 0.500 -> 0.25
zero_rate >  0.500 -> 0.05
zero_rate missing   -> missing
```

A high zero rate can indicate inactive meters, data outages, or NMIs that are poor candidates for individual forecasting.

### zero_run_score

This comes from `longest_zero_run_hours`.

The fixed-threshold rule is:

```text
longest_zero_run_hours <= 12  -> 1.00
longest_zero_run_hours <= 24  -> 0.90
longest_zero_run_hours <= 72  -> 0.70
longest_zero_run_hours <= 168 -> 0.40
longest_zero_run_hours >  168 -> 0.10
longest_zero_run_hours missing -> missing
```

A short zero period may be harmless, but a long run of zeros often indicates inactivity or a data issue.

### outlier_score

This comes from `outlier_rate`.

Outliers are detected with the IQR rule. Lower outlier rate gives a higher score:

```text
outlier_rate <= 0.005 -> 1.00
outlier_rate <= 0.010 -> 0.90
outlier_rate <= 0.030 -> 0.75
outlier_rate <= 0.050 -> 0.50
outlier_rate <= 0.100 -> 0.25
outlier_rate >  0.100 -> 0.05
outlier_rate missing   -> missing
```

Design rationale: data quality has direct operational meaning, so fixed thresholds are easier to interpret than pure ranking. For example, a 20% missing rate should be penalised strongly regardless of how it ranks against other NMIs.

## history_score

`history_score` measures whether the NMI has enough usable and recent historical data.

It is the average of three sub-scores:

```text
history_score = mean(active_years_score, recent_coverage_score, validation_months_score)
```

Missing sub-scores are skipped.

### active_years_score

This comes from `active_years`.

Rule:

```text
active_years: higher is better
uses percentile_score(higher_is_better=True)
longer active history -> higher percentile rank -> score closer to 1
active_years missing -> active_years_score missing
```

The active window runs from the first non-zero reading to the last non-zero reading.

### recent_coverage_score

This comes from `recent_coverage_24m`.

Rule:

```text
recent_coverage_24m: higher is better
uses percentile_score(higher_is_better=True)
better coverage in the most recent 24 months -> score closer to 1
recent_coverage_24m missing -> recent_coverage_score missing
```

### validation_months_score

This comes from `validation_months` in the baseline backtesting step.

Rule:

```text
validation_months: higher is better
uses percentile_score(higher_is_better=True)
more validation months -> score closer to 1
validation_months missing -> validation_months_score missing
```

Design rationale: history length does not have one perfect absolute threshold. The difference between 4 and 5 years is not as clear-cut as a missing-rate threshold, so relative ranking is more stable.

## temporal_pattern_score

`temporal_pattern_score` measures whether the load series has learnable time patterns.

It is the average of five sub-scores:

```text
temporal_pattern_score = mean(
  lag_48_score,
  lag_336_score,
  daily_cycle_score,
  weekly_pattern_score,
  seasonality_score
)
```

Missing sub-scores are skipped.

### lag_48_score

This comes from `abs(lag_48_corr)`.

Rule:

```text
abs(lag_48_corr): higher is better
uses percentile_score(higher_is_better=True)
stronger same-half-hour-yesterday correlation -> score closer to 1
lag_48_corr missing -> lag_48_score missing
```

There are 48 half-hour intervals in one day, so this measures similarity between the current half-hour and the same half-hour yesterday.

### lag_336_score

This comes from `abs(lag_336_corr)`.

Rule:

```text
abs(lag_336_corr): higher is better
uses percentile_score(higher_is_better=True)
stronger same-half-hour-last-week correlation -> score closer to 1
lag_336_corr missing -> lag_336_score missing
```

There are 336 half-hour intervals in one week, so this measures similarity between the current half-hour and the same half-hour last week.

### daily_cycle_score

This comes from `daily_cycle_strength`.

Rule:

```text
daily_cycle_strength: higher is better
uses percentile_score(higher_is_better=True)
clearer daily load shape -> score closer to 1
daily_cycle_strength missing -> daily_cycle_score missing
```

For example, an office building with higher daytime load and lower night load has a clear daily cycle.

### weekly_pattern_score

This comes from `weekly_pattern_strength`.

Rule:

```text
weekly_pattern_strength: higher is better
uses percentile_score(higher_is_better=True)
more stable weekday/weekend or day-of-week pattern -> score closer to 1
weekly_pattern_strength missing -> weekly_pattern_score missing
```

### seasonality_score

This comes from `seasonality_strength`.

Rule:

```text
seasonality_strength: higher is better
uses percentile_score(higher_is_better=True)
more stable monthly or seasonal variation -> score closer to 1
seasonality_strength missing -> seasonality_score missing
```

Design rationale: stronger repeating patterns are easier for forecasting models to learn, and usually lead to more stable forecasts.

## stability_score

`stability_score` measures whether the load pattern is stable over time.

It is the average of three sub-scores:

```text
stability_score = mean(trend_score, yearly_variation_score, structural_break_score_scaled)
```

Missing sub-scores are skipped.

### trend_score

This comes from `trend_strength`.

Rule:

```text
trend_strength: lower is better
uses percentile_score(higher_is_better=False)
weaker long-term trend -> score closer to 1
trend_strength missing -> trend_score missing
```

A stronger long-term trend means the load level is changing more over time.

### yearly_variation_score

This comes from `yearly_variation`.

Rule:

```text
yearly_variation: lower is better
uses percentile_score(higher_is_better=False)
smaller year-to-year variation -> score closer to 1
yearly_variation missing -> yearly_variation_score missing
```

Higher year-to-year variation means the NMI is less stable.

### structural_break_score_scaled

This comes from `structural_break_score`.

Rule:

```text
structural_break_score: lower is better
uses percentile_score(higher_is_better=False)
smaller maximum rolling-mean break -> score closer to 1
structural_break_score missing -> structural_break_score_scaled missing
```

This metric uses the largest change in rolling mean to detect large structural shifts.

Design rationale: stability does not mean the load must never change. It means changes should not be too abrupt or too large. If an NMI has repeated sharp breaks, models trained on historical data are more likely to become unreliable.

## mapping_score

`mapping_score` measures how clearly the NMI can be mapped to buildings.

The script merges mapping information from several sources:

```text
building_nmi_mapping.json
LMS Serial to NMI Map.xlsx
Parkville Substation Mapping.xlsx
Archibus building metadata
```

Each NMI receives a `mapping_quality` label, which is converted into a score:

```text
one_building_mapped                 -> 1.00
many_to_one                         -> 0.80
multi_building_mapped               -> 0.65
substation_shared_multi_building    -> 0.55
many_to_many                        -> 0.45
unknown                             -> 0.30
unmapped                            -> 0.20
other or missing                    -> 0.30
```

Design rationale: clear mapping makes the forecast easier to explain and makes it easier to use building type, campus, and operational context in later modelling. Poor mapping does not always mean the time series is impossible to forecast, so this component has a relatively small weight of 5%.

## How These Scores Become Tiers

The script does not simply sort every NMI by total score. It first applies hard rules for clearly unsuitable or short-history cases.

### Exclude / Needs Review

An NMI is directly assigned to `Exclude / Needs Review` if any of these conditions are true:

```text
status is Dead or Mostly inactive
active_years < 0.25
zero_rate >= 0.80
```

These are severe activity or data issues, so they are handled before score-based ranking.

### Tier C - Short-history candidate

If the NMI is not excluded but satisfies any of these conditions, it is assigned to Tier C:

```text
active_years < 1.0
validation_months < 3
best_baseline_WAPE is missing
```

Tier C does not necessarily mean the data is poor. It mainly means the history or backtesting window is too short for confident individual-model evaluation. These NMIs are better suited to pooled or global models.

### Tier A / B / D

Only the remaining eligible NMIs are classified by `forecastability_score` quantiles:

```text
score >= q75 -> Tier A - Strong forecasting candidate
score <= q25 -> Tier D - Difficult forecasting candidate
otherwise    -> Tier B - Usable with caution
```

Where:

```text
q75 = 75th percentile of forecastability_score among eligible NMIs
q25 = 25th percentile of forecastability_score among eligible NMIs
```

Design rationale: the script first separates inactive, problematic, and short-history NMIs. It then ranks the genuinely comparable NMIs into A, B, and D groups.

## What the Tuning Agent Later Adjusts

This threshold script provides the initial, interpretable classification. The later `score_tuning_agent` and `final_test_driver` mainly tune:

```text
the six component weights
strict/base/lenient profiles for data-quality thresholds
Tier D and Tier A quantile cut points
```

In short, this script gives a transparent baseline classification, and the tuning stage uses CV review feedback to make the final classification better aligned with visual audit results.
