from __future__ import annotations

from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parent
PLAN_PATH = AGENT_DIR / "PROJECT_PLAN.md"

PLAN = """# Score Tuning Agent Project Plan

## Goal

Tune the `forecastability_score` weights and the absolute data-quality thresholds used by
`EDA_Tasks/nmi_score_classification_threshold.py`, using the CV review report produced by the
CV review agent.

The tuning agent does not inspect charts directly. It uses the CV report as the review signal.

## Minimal Folder Structure

```text
nmi_agent_project/
  cv_review_agent/
    nmi_classification_cv_agent.py
    nmi_classification_cv_agent_api_key.txt
    requirements.txt
    README.md
    outputs/
  score_tuning_agent/
    project_planner_agent.py
    score_tuning_agent.py
    README.md
    PROJECT_PLAN.md
    config/
      search_space.json
    prompts/
      tuning_system_prompt.md
    skills/
      scoring_logic.py
    outputs/
```

## File Responsibilities

- `project_planner_agent.py`: writes this plan and defines the project boundary.
- `score_tuning_agent.py`: command-line entry point for tuning.
- `skills/scoring_logic.py`: deterministic scoring, classification, and objective functions.
- `config/search_space.json`: explicit candidate weights and threshold profiles.
- `prompts/tuning_system_prompt.md`: optional LLM prompt for explaining the selected configuration.
- `outputs/`: tuned config, tuned classification table, and tuning report.

## Inputs

- `EDA_Tasks/NMI_score_classification_results/NMI_forecastability_summary_threshold.csv`
- `nmi_agent_project/cv_review_agent/outputs/NMI_classification_cv_review/NMI_classification_cv_review.csv`

## Outputs

- `outputs/optimized_scoring_config.json`
- `outputs/NMI_forecastability_summary_tuned.csv`
- `outputs/tuning_report.csv`
- `outputs/tuning_summary.md`

## Tuning Objective

- If CV judgement is `reasonable`, preserve the current tier.
- If CV judgement is `not_reasonable`, move the NMI away from the current tier.
- If CV judgement is `questionable`, prefer a move away from the current tier with lower weight.

This is intentionally minimal because the CV report has no separate target-tier column.
"""


def main():
    PLAN_PATH.write_text(PLAN, encoding="utf-8")
    print(PLAN_PATH)


if __name__ == "__main__":
    main()
