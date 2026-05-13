from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


WEIGHT_COLUMNS = [
    "performance_score",
    "data_quality_score",
    "history_score",
    "temporal_pattern_score",
    "stability_score",
    "mapping_score",
]

REQUIRED_SUMMARY_COLUMNS = [
    "NMI",
    "forecastability_tier",
    "best_baseline_WAPE",
    "missing_rate",
    "zero_rate",
    "longest_zero_run_hours",
    "outlier_rate",
    "history_score",
    "temporal_pattern_score",
    "stability_score",
    "mapping_score",
    "status",
    "active_years",
    "validation_months",
]

REQUIRED_CV_COLUMNS = [
    "NMI",
    "classified_tier",
    "cv_judgement",
    "cv_reason",
]


@dataclass(frozen=True)
class ScoringConfig:
    weights: dict[str, float]
    threshold_profiles: dict[str, str]
    tier_d_quantile: float
    tier_a_quantile: float
    mode: str = "random"


@dataclass(frozen=True)
class EvaluationResult:
    objective: float
    cv_alignment_score: float
    change_rate: float
    reviewed_count: int
    tier_d_count: int


def validate_columns(frame: pd.DataFrame, required_columns: list[str], name: str) -> None:
    missing = [col for col in required_columns if col not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Weight sum must be positive.")
    return {col: value / total for col, value in weights.items()}


def minmax_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    score = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.dropna()

    if valid.empty:
        return score
    if valid.min() == valid.max():
        score.loc[valid.index] = 0.5
        return score

    scaled = (valid - valid.min()) / (valid.max() - valid.min())
    score.loc[valid.index] = scaled if higher_is_better else 1 - scaled
    return score.clip(0, 1)


def threshold_score(series: pd.Series, thresholds: list[float | None], score_levels: list[float]) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    scores = pd.Series(np.nan, index=values.index, dtype=float)

    for upper, score in zip(thresholds, score_levels):
        limit = np.inf if upper is None else upper
        mask = values.notna() & scores.isna() & (values <= limit)
        scores.loc[mask] = score

    return scores


def recompute_scores(summary: pd.DataFrame, config: ScoringConfig, search_space: dict) -> pd.DataFrame:
    scored = summary.copy()
    profiles = search_space["threshold_profiles"]
    score_levels = search_space["score_levels"]

    scored["performance_score"] = minmax_score(scored["best_baseline_WAPE"], higher_is_better=False)
    scored["missing_score"] = threshold_score(
        scored["missing_rate"],
        profiles["missing_rate"][config.threshold_profiles["missing_rate"]],
        score_levels,
    )
    scored["zero_score"] = threshold_score(
        scored["zero_rate"],
        profiles["zero_rate"][config.threshold_profiles["zero_rate"]],
        score_levels,
    )
    scored["zero_run_score"] = threshold_score(
        scored["longest_zero_run_hours"],
        profiles["longest_zero_run_hours"][config.threshold_profiles["longest_zero_run_hours"]],
        score_levels[:5],
    )
    scored["outlier_score"] = threshold_score(
        scored["outlier_rate"],
        profiles["outlier_rate"][config.threshold_profiles["outlier_rate"]],
        score_levels,
    )
    scored["data_quality_score"] = scored[[
        "missing_score", "zero_score", "zero_run_score", "outlier_score"
    ]].mean(axis=1, skipna=True)

    weights = normalise_weights(config.weights)
    numerator = sum(scored[col] * weight for col, weight in weights.items())
    denominator = sum(weight * scored[col].notna().astype(float) for col, weight in weights.items())
    scored["tuned_forecastability_score"] = numerator / denominator.replace(0, np.nan)
    scored["tuned_score_confidence"] = denominator

    return classify(scored, config.tier_d_quantile, config.tier_a_quantile)


def classify(scored: pd.DataFrame, tier_d_quantile: float, tier_a_quantile: float) -> pd.DataFrame:
    classified = scored.copy()
    classified["tuned_forecastability_tier"] = pd.NA

    exclude_mask = (
        classified["status"].isin(["Dead", "Mostly inactive"])
        | (classified["active_years"] < 0.25)
        | (classified["zero_rate"] >= 0.80)
    )
    classified.loc[exclude_mask, "tuned_forecastability_tier"] = "Exclude / Needs Review"

    short_history_mask = (
        classified["tuned_forecastability_tier"].isna()
        & (
            (classified["active_years"] < 1.0)
            | (classified["validation_months"].fillna(0) < 3)
            | (classified["best_baseline_WAPE"].isna())
        )
    )
    classified.loc[short_history_mask, "tuned_forecastability_tier"] = "Tier C - Short-history candidate"

    eligible_mask = (
        classified["tuned_forecastability_tier"].isna()
        & classified["tuned_forecastability_score"].notna()
    )
    eligible_scores = classified.loc[eligible_mask, "tuned_forecastability_score"]

    if len(eligible_scores) >= 4:
        qd = eligible_scores.quantile(tier_d_quantile)
        qa = eligible_scores.quantile(tier_a_quantile)
        classified.loc[
            eligible_mask & (classified["tuned_forecastability_score"] >= qa),
            "tuned_forecastability_tier",
        ] = "Tier A - Strong forecasting candidate"
        classified.loc[
            eligible_mask & (classified["tuned_forecastability_score"] <= qd),
            "tuned_forecastability_tier",
        ] = "Tier D - Difficult forecasting candidate"
        classified.loc[
            classified["tuned_forecastability_tier"].isna() & eligible_mask,
            "tuned_forecastability_tier",
        ] = "Tier B - Usable with caution"
    else:
        classified.loc[eligible_mask, "tuned_forecastability_tier"] = "Tier B - Usable with caution"

    classified["tuned_forecastability_tier"] = classified["tuned_forecastability_tier"].fillna(
        "Exclude / Needs Review"
    )
    return classified


def review_alignment_table(classified: pd.DataFrame, cv_report: pd.DataFrame) -> pd.DataFrame:
    reviewed = cv_report[REQUIRED_CV_COLUMNS].merge(
        classified[["NMI", "forecastability_tier", "tuned_forecastability_tier", "tuned_forecastability_score"]],
        on="NMI",
        how="inner",
    )
    reviewed["original_tier_family"] = reviewed["classified_tier"].apply(tier_family)
    reviewed["tuned_tier_family"] = reviewed["tuned_forecastability_tier"].apply(tier_family)
    reviewed["target_tier_family"] = reviewed.apply(infer_target_tier_family, axis=1)
    reviewed["tier_changed"] = reviewed["tuned_forecastability_tier"] != reviewed["classified_tier"]
    reviewed["alignment_points"] = reviewed.apply(alignment_points, axis=1)
    return reviewed


def tier_family(tier: str) -> str:
    text = str(tier)
    if text.startswith("Tier A"):
        return "A"
    if text.startswith("Tier B"):
        return "B"
    if text.startswith("Tier C"):
        return "C"
    if text.startswith("Tier D"):
        return "D"
    return "Exclude"


def infer_target_tier_family(row: pd.Series) -> str:
    if row["cv_judgement"] == "reasonable":
        return row["original_tier_family"]

    reason = str(row["cv_reason"]).lower()
    if "tier b" in reason or "usable with caution" in reason:
        return "B"
    if "tier c" in reason or "short-history" in reason or "short history" in reason:
        return "C"
    if "tier a" in reason and "too optimistic" not in reason:
        return "A"
    if "tier d" in reason or "difficult" in reason:
        return "D"
    if "exclude" in reason or "needs review" in reason:
        return "Exclude"
    return row["original_tier_family"]


def alignment_points(row: pd.Series) -> float:
    judgement = row["cv_judgement"]
    changed = bool(row["tier_changed"])
    target_matched = row["tuned_tier_family"] == row["target_tier_family"]

    if judgement == "reasonable":
        return 3.0 if not changed else -2.0
    if judgement == "not_reasonable":
        if target_matched and changed:
            return 6.0
        return 2.0 if changed else -5.0
    if judgement == "questionable":
        if target_matched and changed:
            return 2.0
        return 0.5 if changed else -0.25
    raise ValueError(f"Unexpected cv_judgement: {judgement}")


def evaluate_config(
    summary: pd.DataFrame,
    cv_report: pd.DataFrame,
    config: ScoringConfig,
    search_space: dict,
) -> tuple[EvaluationResult, pd.DataFrame, pd.DataFrame]:
    classified = recompute_scores(summary, config, search_space)
    reviewed = review_alignment_table(classified, cv_report)
    if reviewed.empty:
        raise ValueError("No overlapping NMI rows between summary table and CV report.")

    cv_alignment_score = float(reviewed["alignment_points"].sum())
    change_rate = float((classified["tuned_forecastability_tier"] != classified["forecastability_tier"]).mean())
    objective = cv_alignment_score - search_space["change_penalty"] * change_rate
    tier_d_count = int(classified["tuned_forecastability_tier"].str.startswith("Tier D").sum())

    result = EvaluationResult(
        objective=objective,
        cv_alignment_score=cv_alignment_score,
        change_rate=change_rate,
        reviewed_count=len(reviewed),
        tier_d_count=tier_d_count,
    )
    return result, classified, reviewed


def neighbor_configs(config: ScoringConfig, search_space: dict):
    step = search_space["weight_step"]

    for component in WEIGHT_COLUMNS:
        for delta in (-step, step):
            weights = dict(config.weights)
            weights[component] = weights[component] + delta
            if weights[component] <= 0:
                continue
            yield ScoringConfig(
                weights=normalise_weights(weights),
                threshold_profiles=dict(config.threshold_profiles),
                tier_d_quantile=config.tier_d_quantile,
                tier_a_quantile=config.tier_a_quantile,
                mode="neighbor",
            )

    for metric, profiles in search_space["threshold_profiles"].items():
        for profile_name in profiles:
            if config.threshold_profiles[metric] == profile_name:
                continue
            threshold_profiles = dict(config.threshold_profiles)
            threshold_profiles[metric] = profile_name
            yield ScoringConfig(
                weights=dict(config.weights),
                threshold_profiles=threshold_profiles,
                tier_d_quantile=config.tier_d_quantile,
                tier_a_quantile=config.tier_a_quantile,
                mode="neighbor",
            )


def random_config(rng: np.random.Generator, search_space: dict, mode: str) -> ScoringConfig:
    raw_weights = rng.dirichlet(np.ones(len(WEIGHT_COLUMNS)))
    weights = dict(zip(WEIGHT_COLUMNS, raw_weights))
    threshold_profiles = {
        metric: str(rng.choice(list(profiles.keys())))
        for metric, profiles in search_space["threshold_profiles"].items()
    }
    return ScoringConfig(
        weights=normalise_weights(weights),
        threshold_profiles=threshold_profiles,
        tier_d_quantile=float(rng.choice(search_space["tier_d_quantile_values"])),
        tier_a_quantile=float(rng.choice(search_space["tier_a_quantile_values"])),
        mode=mode,
    )


def logic_config(search_space: dict) -> ScoringConfig:
    return ScoringConfig(
        weights=normalise_weights(search_space["logic_weights"]),
        threshold_profiles=dict(search_space["logic_threshold_profiles"]),
        tier_d_quantile=float(search_space["logic_tier_quantiles"]["tier_d_quantile"]),
        tier_a_quantile=float(search_space["logic_tier_quantiles"]["tier_a_quantile"]),
        mode="logic",
    )


def history_row(iteration: int, evaluation: EvaluationResult, config: ScoringConfig, accepted: bool) -> dict:
    return {
        "iteration": iteration,
        "objective": evaluation.objective,
        "cv_alignment_score": evaluation.cv_alignment_score,
        "change_rate": evaluation.change_rate,
        "tier_d_count": evaluation.tier_d_count,
        "weights": config.weights,
        "threshold_profiles": config.threshold_profiles,
        "tier_d_quantile": config.tier_d_quantile,
        "tier_a_quantile": config.tier_a_quantile,
        "mode": config.mode,
        "accepted": accepted,
    }


def tune(summary: pd.DataFrame, cv_report: pd.DataFrame, search_space: dict, strategy: str = "random"):
    validate_columns(summary, REQUIRED_SUMMARY_COLUMNS, "summary table")
    validate_columns(cv_report, REQUIRED_CV_COLUMNS, "CV report")

    if strategy == "logic":
        config = logic_config(search_space)
        evaluation, classified, reviewed = evaluate_config(summary, cv_report, config, search_space)
        return config, evaluation, classified, reviewed, pd.DataFrame([
            history_row(0, evaluation, config, True)
        ])

    if strategy != "random":
        raise ValueError("strategy must be 'random' or 'logic'.")

    rng = np.random.default_rng(search_space["random_seed"])
    best_config = random_config(rng, search_space, "random_initial")
    best_eval, best_classified, best_reviewed = evaluate_config(summary, cv_report, best_config, search_space)
    history = [history_row(0, best_eval, best_config, True)]

    for iteration in range(1, search_space["random_trials"] + 1):
        config = random_config(rng, search_space, "random")
        evaluation, classified, reviewed = evaluate_config(summary, cv_report, config, search_space)
        accepted = evaluation.objective > best_eval.objective

        if accepted:
            best_config = config
            best_eval = evaluation
            best_classified = classified
            best_reviewed = reviewed

        history.append(history_row(iteration, evaluation, config, accepted))

    return best_config, best_eval, best_classified, best_reviewed, pd.DataFrame(history)
