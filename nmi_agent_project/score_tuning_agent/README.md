# Score Tuning Agent

This agent tunes the `forecastability_score` weights and the absolute data-quality threshold profiles after the CV review agent has produced its report.

## Structure

```text
score_tuning_agent/
  project_planner_agent.py
  PROJECT_PLAN.md
  score_tuning_agent.py
  config/
    search_space.json
  prompts/
    tuning_system_prompt.md
  skills/
    scoring_logic.py
  outputs/
```

## Inputs

Default inputs:

- `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary_threshold.csv`
- `nmi_agent_project/cv_review_agent/outputs/NMI_classification_cv_review/NMI_classification_cv_review.csv`

The CV report must contain:

- `NMI`
- `classified_tier`
- `cv_judgement`
- `cv_reason`

## Objective

- `reasonable`: keep the current tier.
- `not_reasonable`: prefer a changed tier, and use the free-text CV reason to infer the target tier when it names one.
- `questionable`: prefer a target-matching tier change with lower weight.

The CV report does not include an explicit target-tier column, so `skills/scoring_logic.py` infers a target tier family from `cv_reason` when the reason mentions Tier A/B/C/D or Exclude/Needs Review.

## Run

```powershell
python nmi_agent_project\score_tuning_agent\project_planner_agent.py
python nmi_agent_project\score_tuning_agent\score_tuning_agent.py
```

Use custom inputs:

```powershell
python nmi_agent_project\score_tuning_agent\score_tuning_agent.py `
  --summary-csv EDA_Tasks\NMI_score_classification_results\NMI_forecastability_summary_threshold.csv `
  --cv-report-csv nmi_agent_project\cv_review_agent\outputs\NMI_classification_cv_review\NMI_classification_cv_review.csv
```

## Outputs

- `outputs/optimized_scoring_config_random.json`
- `outputs/NMI_forecastability_summary_tuned_random.csv`
- `outputs/tuning_report_random.csv`
- `outputs/tuning_history_random.csv`
- `outputs/tuning_summary_random.md`

Use `--strategy logic` for the deterministic logic-weight variant; it writes the same filenames with a `_logic` suffix.

The final closed-loop run no longer reads start config from this output folder. Its stable start and final configs are stored under `nmi_agent_project/final_test/config/`.
