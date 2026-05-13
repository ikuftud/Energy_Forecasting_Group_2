from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from skills.scoring_logic import tune


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = AGENT_DIR / "outputs"

DEFAULT_SUMMARY_CSV = (
    PROJECT_ROOT
    / "EDA_Tasks"
    / "NMI_score_classification_results"
    / "NMI_forecastability_summary_threshold.csv"
)
DEFAULT_CV_REPORT_CSV = (
    PROJECT_ROOT
    / "nmi_agent_project"
    / "cv_review_agent"
    / "outputs"
    / "NMI_classification_cv_review"
    / "NMI_classification_cv_review.csv"
)
DEFAULT_SEARCH_SPACE = AGENT_DIR / "config" / "search_space.json"

def parse_args():
    parser = argparse.ArgumentParser(description="Tune NMI forecastability weights and data-quality thresholds.")
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--cv-report-csv", type=Path, default=DEFAULT_CV_REPORT_CSV)
    parser.add_argument("--search-space", type=Path, default=DEFAULT_SEARCH_SPACE)
    parser.add_argument("--strategy", choices=["random", "logic"], default="random")
    return parser.parse_args()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def summary_markdown(config, evaluation, reviewed):
    judgement_counts = reviewed["cv_judgement"].value_counts().to_dict()
    changed_counts = reviewed.groupby("cv_judgement")["tier_changed"].sum().astype(int).to_dict()

    lines = [
        "# Score Tuning Summary",
        "",
        "## Selected Weights",
        "",
    ]
    for name, value in config.weights.items():
        lines.append(f"- `{name}`: {value:.6f}")

    lines.extend([
        "",
        "## Selected Threshold Profiles",
        "",
    ])
    for name, value in config.threshold_profiles.items():
        lines.append(f"- `{name}`: `{value}`")

    lines.extend([
        "",
        "## Objective",
        "",
        f"- `objective`: {evaluation.objective:.6f}",
        f"- `cv_alignment_score`: {evaluation.cv_alignment_score:.6f}",
        f"- `change_rate`: {evaluation.change_rate:.6f}",
        f"- `reviewed_count`: {evaluation.reviewed_count}",
        f"- `tier_d_count`: {evaluation.tier_d_count}",
        f"- `tier_d_quantile`: {config.tier_d_quantile:.2f}",
        f"- `tier_a_quantile`: {config.tier_a_quantile:.2f}",
        "",
        "## CV Review Counts",
        "",
    ])
    for judgement, count in judgement_counts.items():
        lines.append(f"- `{judgement}`: {count}, changed by tuned config: {changed_counts.get(judgement, 0)}")

    lines.extend([
        "",
        "## Limitation",
        "",
        "The CV report contains judgement labels and free-text reasons, but no explicit target-tier column. "
        "The tuning objective preserves reasonable rows and infers target tier direction from CV reasons for "
        "questionable and not_reasonable rows.",
    ])
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = pd.read_csv(args.summary_csv)
    cv_report = pd.read_csv(args.cv_report_csv)
    search_space = read_json(args.search_space)

    config, evaluation, tuned_summary, tuning_report, history = tune(
        summary, cv_report, search_space, strategy=args.strategy
    )

    suffix = args.strategy
    optimized_config_json = OUTPUT_DIR / f"optimized_scoring_config_{suffix}.json"
    tuned_summary_csv = OUTPUT_DIR / f"NMI_forecastability_summary_tuned_{suffix}.csv"
    tuning_report_csv = OUTPUT_DIR / f"tuning_report_{suffix}.csv"
    tuning_history_csv = OUTPUT_DIR / f"tuning_history_{suffix}.csv"
    tuning_summary_md = OUTPUT_DIR / f"tuning_summary_{suffix}.md"

    tuned_summary.to_csv(tuned_summary_csv, index=False)
    tuning_report.to_csv(tuning_report_csv, index=False)
    history.to_csv(tuning_history_csv, index=False)
    write_json(optimized_config_json, {
        "weights": config.weights,
        "threshold_profiles": config.threshold_profiles,
        "tier_d_quantile": config.tier_d_quantile,
        "tier_a_quantile": config.tier_a_quantile,
        "strategy": args.strategy,
        "objective": evaluation.objective,
        "cv_alignment_score": evaluation.cv_alignment_score,
        "change_rate": evaluation.change_rate,
        "reviewed_count": evaluation.reviewed_count,
        "tier_d_count": evaluation.tier_d_count,
    })
    tuning_summary_md.write_text(summary_markdown(config, evaluation, tuning_report), encoding="utf-8")

    print("Saved optimized config:", optimized_config_json)
    print("Saved tuned summary:", tuned_summary_csv)
    print("Saved tuning report:", tuning_report_csv)
    print("Saved tuning history:", tuning_history_csv)
    print("Saved tuning summary:", tuning_summary_md)


if __name__ == "__main__":
    main()
