# Final Test Driver

`final_test_driver.py` runs the final closed-loop NMI review mode:

1. Start from `config/start_config_random.json`.
2. Recompute the classification table for the current config.
3. Run chart-based CV review for every NMI.
4. Run random score tuning.
5. Repeat until the tuned tiers stop changing, with a forced minimum of two full rounds.

## Final Run Mode

The final project run used:

```powershell
python nmi_agent_project\final_test\final_test_driver.py
```

This preserves the archived-session decision:

- force at least two complete CV review + random tuning rounds;
- stop after round 2 if the config/tier output has converged;
- keep `--max-loops` at 5;
- use `--random-trials 10000` in final-test runs without changing `score_tuning_agent/config/search_space.json`;
- write each run into an independent timestamped output directory.

Use `--output-dir` when the run needs a specific name:

```powershell
python nmi_agent_project\final_test\final_test_driver.py `
  --min-loops 2 `
  --max-loops 5 `
  --random-trials 10000 `
  --output-dir nmi_agent_project\final_test\outputs\forced_two_rounds_10000_YYYYMMDD_HHMMSS
```

## Last Completed Run

The final accepted run was:

```text
nmi_agent_project/final_test/outputs/forced_two_rounds_10000_20260513_024713/
```

It completed 2 iterations and converged on the second iteration:

| iteration | objective | cv_alignment_score | change_rate | tier_d_count | changed_count | converged |
|---:|---:|---:|---:|---:|---:|:---|
| 1 | 245.748485 | 245.75 | 0.050505 | 10 | 5 | false |
| 2 | 245.000000 | 245.00 | 0.000000 | 10 | 0 | true |

The stable final config is copied to `config/final_scoring_config.json` so the selected weights and threshold profiles are available without relying on generated output folders.

## Output Layout

Each run writes:

```text
outputs/<run_id>/
  iteration_1/
    classification_input_1.csv
    cv_review_1.csv
    cv_review_1.xlsx
    input_config_1.json
    optimized_config_1.json
    tuned_summary_1.csv
    tuning_report_1.csv
    tuning_history_1.csv
    plots_1/
  iteration_2/
  final_test_loop_summary.csv
  final_test_final_config.json
  run.stdout.log
  run.stderr.log
```

The output folders are generated artifacts. Keep them locally for audit, but do not treat them as source files.
