from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = PROJECT_ROOT / "nmi_agent_project"
CV_AGENT_DIR = AGENT_ROOT / "cv_review_agent"
TUNING_AGENT_DIR = AGENT_ROOT / "score_tuning_agent"
FINAL_TEST_DIR = AGENT_ROOT / "final_test"
FINAL_TEST_CONFIG_DIR = FINAL_TEST_DIR / "config"

sys.path.insert(0, str(CV_AGENT_DIR))
sys.path.insert(0, str(TUNING_AGENT_DIR))

import nmi_classification_cv_agent as cv_agent
from skills.scoring_logic import ScoringConfig, recompute_scores, tune


SUMMARY_CSV = PROJECT_ROOT / "EDA_Tasks" / "NMI_score_classification_results" / "NMI_forecastability_summary_threshold.csv"
SEARCH_SPACE_JSON = TUNING_AGENT_DIR / "config" / "search_space.json"
START_CONFIG_JSON = FINAL_TEST_CONFIG_DIR / "start_config_random.json"
OUTPUT_DIR = FINAL_TEST_DIR / "outputs"


def parse_args():
    parser = argparse.ArgumentParser(description="Run final_test iterative CV review and random tuning loop.")
    parser.add_argument("--max-loops", type=int, default=5)
    parser.add_argument("--min-loops", type=int, default=2)
    parser.add_argument("--random-trials", type=int, default=10000)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--start-config", type=Path, default=START_CONFIG_JSON)
    parser.add_argument("--model", default=cv_agent.DEFAULT_MODEL)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def to_jsonable(value):
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def config_from_json(payload: dict, mode: str) -> ScoringConfig:
    if "final_config" in payload:
        payload = payload["final_config"]
    return ScoringConfig(
        weights={key: float(value) for key, value in payload["weights"].items()},
        threshold_profiles=dict(payload["threshold_profiles"]),
        tier_d_quantile=float(payload["tier_d_quantile"]),
        tier_a_quantile=float(payload["tier_a_quantile"]),
        mode=mode,
    )


def config_payload(config: ScoringConfig, evaluation=None):
    payload = {
        "weights": config.weights,
        "threshold_profiles": config.threshold_profiles,
        "tier_d_quantile": config.tier_d_quantile,
        "tier_a_quantile": config.tier_a_quantile,
        "mode": config.mode,
    }
    if evaluation is not None:
        payload.update({
            "objective": evaluation.objective,
            "cv_alignment_score": evaluation.cv_alignment_score,
            "change_rate": evaluation.change_rate,
            "reviewed_count": evaluation.reviewed_count,
            "tier_d_count": evaluation.tier_d_count,
        })
    return payload


def config_signature(config: ScoringConfig):
    weights = tuple(round(float(config.weights[col]), 10) for col in sorted(config.weights))
    profiles = tuple((key, config.threshold_profiles[key]) for key in sorted(config.threshold_profiles))
    return weights, profiles, round(config.tier_d_quantile, 10), round(config.tier_a_quantile, 10)


def prepare_classification_input(summary: pd.DataFrame, config: ScoringConfig, search_space: dict, iteration_dir: Path, iteration: int):
    tuned = recompute_scores(summary, config, search_space)
    cv_input = tuned.copy()
    cv_input["source_forecastability_tier"] = cv_input["forecastability_tier"]
    cv_input["forecastability_tier"] = cv_input["tuned_forecastability_tier"]
    cv_input["forecastability_score"] = cv_input["tuned_forecastability_score"]
    cv_input["score_confidence"] = cv_input["tuned_score_confidence"]

    input_path = iteration_dir / f"classification_input_{iteration}.csv"
    cv_input.to_csv(input_path, index=False)
    return cv_input, input_path


def run_cv_review(cv_input: pd.DataFrame, client: OpenAI, model: str, iteration_dir: Path, iteration: int):
    cv_agent.PLOT_DIR = iteration_dir / f"plots_{iteration}"
    cv_agent.PLOT_DIR.mkdir(parents=True, exist_ok=True)

    energy = cv_agent.load_energy()
    rows = []
    total = len(cv_input)

    for index, row in cv_input.reset_index(drop=True).iterrows():
        nmi = str(row["NMI"])
        tier = str(row["forecastability_tier"])
        print(f"[final_test {iteration}] [{index + 1}/{total}] Reviewing {nmi}: {tier}", flush=True)

        image_paths = cv_agent.generate_review_images(energy, row)
        review = cv_agent.review_nmi(client, model, row, image_paths)
        rows.append({
            "NMI": nmi,
            "classified_tier": tier,
            "cv_judgement": review.classification_reasonable,
            "cv_reason": review.reason,
        })

    output = pd.DataFrame(rows, columns=["NMI", "classified_tier", "cv_judgement", "cv_reason"])
    csv_path = iteration_dir / f"cv_review_{iteration}.csv"
    xlsx_path = iteration_dir / f"cv_review_{iteration}.xlsx"
    output.to_csv(csv_path, index=False)
    output.to_excel(xlsx_path, index=False)
    return output, csv_path, xlsx_path


def save_tuning_outputs(iteration_dir: Path, iteration: int, config, evaluation, tuned_summary, tuning_report, history):
    tuned_path = iteration_dir / f"tuned_summary_{iteration}.csv"
    report_path = iteration_dir / f"tuning_report_{iteration}.csv"
    history_path = iteration_dir / f"tuning_history_{iteration}.csv"
    config_path = iteration_dir / f"optimized_config_{iteration}.json"

    tuned_summary.to_csv(tuned_path, index=False)
    tuning_report.to_csv(report_path, index=False)
    history.to_csv(history_path, index=False)
    write_json(config_path, config_payload(config, evaluation))
    return tuned_path, report_path, history_path, config_path


def tier_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame.set_index("NMI")[column].sort_index()


def main():
    args = parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = OUTPUT_DIR / f"final_test_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = pd.read_csv(SUMMARY_CSV)
    if args.limit:
        summary = summary.head(args.limit).copy()

    search_space = read_json(SEARCH_SPACE_JSON)
    if args.random_trials is not None:
        search_space["random_trials"] = args.random_trials
    current_config = config_from_json(read_json(args.start_config), mode="final_test_start_config")
    client = OpenAI(api_key=cv_agent.read_api_key())

    loop_rows = []
    previous_signature = config_signature(current_config)
    converged = False

    for iteration in range(1, args.max_loops + 1):
        iteration_dir = output_dir / f"iteration_{iteration}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        input_config_path = iteration_dir / f"input_config_{iteration}.json"
        write_json(input_config_path, config_payload(current_config))

        cv_input, input_path = prepare_classification_input(summary, current_config, search_space, iteration_dir, iteration)
        cv_report, cv_csv, cv_xlsx = run_cv_review(cv_input, client, args.model, iteration_dir, iteration)

        best_config, evaluation, tuned_summary, tuning_report, history = tune(
            cv_input,
            cv_report,
            search_space,
            strategy="random",
        )
        tuned_path, report_path, history_path, config_path = save_tuning_outputs(
            iteration_dir, iteration, best_config, evaluation, tuned_summary, tuning_report, history
        )

        input_tiers = tier_series(cv_input, "forecastability_tier")
        tuned_tiers = tier_series(tuned_summary, "tuned_forecastability_tier")
        changed_count = int((input_tiers != tuned_tiers).sum())
        signature = config_signature(best_config)
        config_unchanged = signature == previous_signature
        converged = changed_count == 0 or config_unchanged
        should_stop = converged and iteration >= args.min_loops

        loop_rows.append({
            "iteration": iteration,
            "cv_review_csv": str(cv_csv),
            "classification_input_csv": str(input_path),
            "input_config_json": str(input_config_path),
            "optimized_config_json": str(config_path),
            "tuned_summary_csv": str(tuned_path),
            "tuning_report_csv": str(report_path),
            "tuning_history_csv": str(history_path),
            "objective": evaluation.objective,
            "cv_alignment_score": evaluation.cv_alignment_score,
            "change_rate": evaluation.change_rate,
            "tier_d_count": evaluation.tier_d_count,
            "changed_count": changed_count,
            "config_unchanged": config_unchanged,
            "converged": converged,
            "should_stop": should_stop,
            "random_trials": search_space["random_trials"],
        })

        print(
            f"[final_test {iteration}] objective={evaluation.objective:.6f} "
            f"tier_d_count={evaluation.tier_d_count} changed_count={changed_count} "
            f"converged={converged}",
            flush=True,
        )

        current_config = best_config
        previous_signature = signature

        if should_stop:
            break

    loop_summary = pd.DataFrame(loop_rows)
    loop_summary_path = output_dir / "final_test_loop_summary.csv"
    final_config_path = output_dir / "final_test_final_config.json"
    loop_summary.to_csv(loop_summary_path, index=False)
    write_json(final_config_path, {
        "converged": converged,
        "completed_iterations": len(loop_rows),
        "final_config": config_payload(current_config),
        "random_trials": search_space["random_trials"],
        "loop_summary_csv": str(loop_summary_path),
    })

    print("Saved loop summary:", loop_summary_path, flush=True)
    print("Saved final config:", final_config_path, flush=True)


if __name__ == "__main__":
    main()
