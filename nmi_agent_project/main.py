from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "nmi_agent_project"

THRESHOLD_SCRIPT = PROJECT_ROOT / "EDA_Tasks" / "nmi_score_classification_threshold.py"
CV_REVIEW_SCRIPT = AGENT_ROOT / "cv_review_agent" / "nmi_classification_cv_agent.py"
SCORE_TUNING_SCRIPT = AGENT_ROOT / "score_tuning_agent" / "score_tuning_agent.py"
FINAL_TEST_SCRIPT = AGENT_ROOT / "final_test" / "final_test_driver.py"

GENERATED_RANDOM_CONFIG = (
    AGENT_ROOT
    / "score_tuning_agent"
    / "outputs"
    / "optimized_scoring_config_random.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete NMI agent workflow in order."
    )
    parser.add_argument(
        "--min-run",
        "--min-loops",
        dest="min_run",
        type=int,
        default=2,
        help="Minimum number of final_test iterations before convergence can stop the run.",
    )
    parser.add_argument(
        "--max-run",
        "--max-loops",
        dest="max_run",
        type=int,
        default=5,
        help="Maximum number of final_test iterations.",
    )
    parser.add_argument(
        "--output",
        "--output-dir",
        dest="output_dir",
        type=Path,
        help="Optional final_test output directory. Defaults to final_test_driver.py's timestamped directory.",
    )
    parser.add_argument(
        "--random-trials",
        type=int,
        default=10000,
        help="Random tuning trials for each final_test iteration.",
    )
    parser.add_argument(
        "--model",
        help="Optional OpenAI model override for CV review and final_test.",
    )
    args = parser.parse_args()
    validate_args(args, parser)
    return args


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    errors = []
    if args.min_run < 1:
        errors.append("--min-run must be at least 1.")
    if args.max_run < 1:
        errors.append("--max-run must be at least 1.")
    if args.min_run > args.max_run:
        errors.append("--min-run cannot be greater than --max-run.")
    if args.random_trials < 1:
        errors.append("--random-trials must be at least 1.")

    if errors:
        parser.error(" ".join(errors))


def run_step(name: str, command: list[str]) -> None:
    print(f"\n=== {name} ===", flush=True)
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    args = parse_args()

    python = sys.executable

    threshold_cmd = [python, str(THRESHOLD_SCRIPT)]
    cv_cmd = [python, str(CV_REVIEW_SCRIPT)]
    if args.model:
        cv_cmd.extend(["--model", args.model])

    tuning_cmd = [python, str(SCORE_TUNING_SCRIPT), "--strategy", "random"]

    final_cmd = [
        python,
        str(FINAL_TEST_SCRIPT),
        "--min-loops",
        str(args.min_run),
        "--max-loops",
        str(args.max_run),
        "--random-trials",
        str(args.random_trials),
        "--start-config",
        str(GENERATED_RANDOM_CONFIG),
    ]
    if args.output_dir is not None:
        final_cmd.extend(["--output-dir", str(args.output_dir)])
    if args.model:
        final_cmd.extend(["--model", args.model])

    run_step("1/4 Generate threshold classification", threshold_cmd)
    run_step("2/4 Run CV review agent", cv_cmd)
    run_step("3/4 Run score tuning agent", tuning_cmd)
    run_step("4/4 Run final_test loop", final_cmd)

    print("\nComplete NMI agent workflow finished.", flush=True)


if __name__ == "__main__":
    main()
