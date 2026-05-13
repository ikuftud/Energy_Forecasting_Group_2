from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Literal

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "Datasets"
EDA_DIR = PROJECT_ROOT / "EDA_Tasks"
SCORE_DIR = EDA_DIR / "NMI_score_classification_results"
AGENT_DIR = Path(__file__).resolve().parent
REVIEW_DIR = AGENT_DIR / "outputs" / "NMI_classification_cv_review"
PLOT_DIR = REVIEW_DIR / "plots"

ENERGY_CSV = DATA_DIR / "LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv"
CLASSIFICATION_CSV = SCORE_DIR / "NMI_forecastability_summary_threshold.csv"
API_KEY_TXT = AGENT_DIR / "nmi_classification_cv_agent_api_key.txt"
DEFAULT_MODEL = "gpt-5.4-mini"

OUTPUT_CSV = REVIEW_DIR / "NMI_classification_cv_review.csv"
OUTPUT_XLSX = REVIEW_DIR / "NMI_classification_cv_review.xlsx"

METRIC_COLUMNS = [
    "status",
    "active_years",
    "recent_coverage_12m",
    "recent_coverage_24m",
    "missing_rate",
    "zero_rate",
    "longest_zero_run_hours",
    "outlier_rate",
    "lag_48_corr",
    "lag_336_corr",
    "daily_cycle_strength",
    "weekly_pattern_strength",
    "seasonality_strength",
    "trend_strength",
    "yearly_variation",
    "structural_break_score",
    "best_baseline_type",
    "best_baseline_WAPE",
    "performance_score",
    "data_quality_score",
    "history_score",
    "temporal_pattern_score",
    "stability_score",
    "mapping_score",
    "forecastability_score",
    "score_confidence",
]

SYSTEM_PROMPT = """
You are auditing an energy-forecastability classification for one NMI.
Use the supplied charts as the primary visual evidence and the metrics as supporting evidence.

Tier meanings:
- Tier A - Strong forecasting candidate: clear recurring load shape, good data quality, stable enough for individual forecasting.
- Tier B - Usable with caution: forecastable but with visible caveats such as moderate instability, weak seasonality, or some data-quality concerns.
- Tier C - Short-history candidate: not necessarily poor; history or backtesting window is too short for confident individual-model evaluation.
- Tier D - Difficult forecasting candidate: visually noisy, unstable, weak recurring pattern, or high baseline error.
- Exclude / Needs Review: inactive, mostly inactive, severe missing/zero behaviour, or mapping/data issues that should be reviewed first.

Do not over-penalise a single short zero run if the rest of the series is stable and patterned.
Flag the current tier as not_reasonable only when the visual evidence strongly contradicts it.
Flag it as questionable when it is plausible but borderline.
When the tier is questionable or not_reasonable, include the more plausible tier or direction in the reason text if the charts support it.
Return concise JSON-compatible reasoning.
""".strip()


class CVReview(BaseModel):
    nmi: str
    assigned_tier: str
    classification_reasonable: Literal["reasonable", "questionable", "not_reasonable"]
    reason: str


def parse_args():
    parser = argparse.ArgumentParser(description="Audit NMI classifications with chart-based CV reasoning.")
    parser.add_argument("--classification-csv", type=Path, default=CLASSIFICATION_CSV)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--nmi", action="append")
    return parser.parse_args()


def read_api_key():
    api_keys = [
        line.strip()
        for line in API_KEY_TXT.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("sk-")
    ]
    if len(api_keys) != 1:
        raise ValueError(f"Paste the API key into {API_KEY_TXT}")
    return api_keys[0]


def load_energy():
    energy = pd.read_csv(ENERGY_CSV, parse_dates=["date"])
    energy.columns = [
        col.replace(" consumption", "") if col != "date" else col
        for col in energy.columns
    ]
    return energy.sort_values("date").set_index("date")


def load_classification(path):
    classified = pd.read_csv(path)
    classified["NMI"] = classified["NMI"].astype(str)
    return classified


def selected_rows(classified, nmis, limit):
    rows = classified
    if nmis:
        rows = rows[rows["NMI"].isin([str(nmi) for nmi in nmis])]
    if limit:
        rows = rows.head(limit)
    return rows.reset_index(drop=True)


def active_series(energy, nmi):
    series = pd.to_numeric(energy[nmi], errors="coerce").rename(nmi)
    nonzero = series.fillna(0).ne(0)
    if not nonzero.any():
        return series
    return series.loc[series.index[nonzero].min():series.index[nonzero].max()]


def safe_filename(text):
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in str(text))


def generate_review_images(energy, row):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    nmi = str(row["NMI"])
    tier = str(row["forecastability_tier"])
    series = active_series(energy, nmi)
    safe_nmi = safe_filename(nmi)

    deep_dive_path = PLOT_DIR / f"{safe_nmi}_deep_dive.png"
    quality_path = PLOT_DIR / f"{safe_nmi}_quality_diagnostics.png"

    plot_deep_dive(series, nmi, tier, deep_dive_path)
    plot_quality_diagnostics(series, nmi, tier, quality_path)

    return [deep_dive_path, quality_path]


def plot_deep_dive(series, nmi, tier, output_path):
    daily = series.resample("D").sum(min_count=1)
    weekday_hour = (
        series
        .groupby([series.index.hour, series.index.dayofweek < 5])
        .mean()
        .unstack()
        .reindex(index=range(24), columns=[True, False])
    )
    yearly_mean = daily.groupby(daily.index.year).mean()
    year_tod = series.groupby([series.index.year, series.index.time]).mean()
    year_month = series.groupby([series.index.year, series.index.month]).sum()
    years = sorted(series.index.year.unique())
    colors = plt.cm.tab20(np.linspace(0, 1, len(years)))

    fig, axs = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f"{nmi} Deep Dive | {tier}", fontsize=16)

    axs[0, 0].plot(weekday_hour.index, weekday_hour[True], label="weekday")
    axs[0, 0].plot(weekday_hour.index, weekday_hour[False], label="weekend")
    axs[0, 0].set_ylim(0, axs[0, 0].get_ylim()[1] * 1.05)
    axs[0, 0].set_xlabel("hour")
    axs[0, 0].set_ylabel("avg consumption")
    axs[0, 0].set_title("Weekday vs Weekend")
    axs[0, 0].set_xticks(np.arange(0, 24, 2))
    axs[0, 0].legend()

    axs[0, 1].bar(yearly_mean.index.astype(str), yearly_mean.values)
    axs[0, 1].set_title("Yearly Mean Daily Consumption")
    axs[0, 1].set_xlabel("year")
    axs[0, 1].set_ylabel("avg daily consumption")
    axs[0, 1].tick_params(axis="x", rotation=45)

    for color, year in zip(colors, years):
        tod = year_tod.loc[year]
        axs[1, 0].plot(range(len(tod)), tod.values, label=str(year), color=color, lw=1.7)

        monthly = year_month.loc[year]
        axs[1, 1].plot(monthly.index - 1, monthly.values, label=str(year), color=color, lw=1.7)

    axs[1, 0].set_title("Average Daily Load Shape by Year")
    axs[1, 0].set_xlabel("30-minute interval")
    axs[1, 0].set_ylabel("avg consumption")
    axs[1, 0].legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    axs[1, 1].set_title("Monthly Consumption by Year")
    axs[1, 1].set_xlabel("month")
    axs[1, 1].set_ylabel("consumption")
    axs[1, 1].set_xticks(
        list(range(12)),
        labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_quality_diagnostics(series, nmi, tier, output_path):
    daily = series.resample("D").sum(min_count=1)
    rolling_mean = daily.rolling(window=30, min_periods=15).mean()
    rolling_std = daily.rolling(window=30, min_periods=15).std()
    monthly_zero_rate = series.fillna(0).eq(0).groupby(series.index.to_period("M")).mean()
    values = series.dropna()
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    fig, axs = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle(f"{nmi} Quality Diagnostics | {tier}", fontsize=16)

    axs[0, 0].plot(daily.index, daily.values, color="#7f7f7f", alpha=0.55, label="daily total")
    axs[0, 0].plot(rolling_mean.index, rolling_mean.values, color="#1f77b4", lw=2, label="30-day rolling mean")
    axs[0, 0].set_title("Active Daily Total and Rolling Mean")
    axs[0, 0].set_xlabel("date")
    axs[0, 0].set_ylabel("daily consumption")
    axs[0, 0].legend()

    axs[0, 1].plot(rolling_std.index, rolling_std.values, color="#d62728", lw=1.8)
    axs[0, 1].set_title("30-Day Rolling Standard Deviation")
    axs[0, 1].set_xlabel("date")
    axs[0, 1].set_ylabel("rolling std")

    axs[1, 0].plot(monthly_zero_rate.index.to_timestamp(), monthly_zero_rate.values, color="#9467bd", lw=1.8)
    axs[1, 0].set_ylim(0, 1)
    axs[1, 0].set_title("Monthly Zero-Reading Rate")
    axs[1, 0].set_xlabel("month")
    axs[1, 0].set_ylabel("zero rate")

    axs[1, 1].hist(values, bins=60, color="#4c78a8", alpha=0.75)
    axs[1, 1].axvline(lower, color="#d62728", linestyle="--", label="IQR lower")
    axs[1, 1].axvline(upper, color="#d62728", linestyle="--", label="IQR upper")
    axs[1, 1].set_title("Consumption Distribution and IQR Bounds")
    axs[1, 1].set_xlabel("consumption")
    axs[1, 1].set_ylabel("count")
    axs[1, 1].legend()

    plt.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def image_data_url(path):
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def serialise_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def metric_context(row):
    return {
        col: serialise_value(row[col])
        for col in METRIC_COLUMNS
        if col in row.index
    }


def build_user_prompt(row):
    context = {
        "nmi": str(row["NMI"]),
        "assigned_tier": str(row["forecastability_tier"]),
        "metrics": metric_context(row),
    }
    return (
        "Audit whether the assigned tier is reasonable for this NMI.\n"
        "Return the assigned tier unchanged, then judge the reasonableness of that assigned tier.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def review_nmi(client, model, row, image_paths):
    content = [{"type": "input_text", "text": build_user_prompt(row)}]
    content.extend([
        {"type": "input_image", "image_url": image_data_url(path), "detail": "low"}
        for path in image_paths
    ])

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        max_output_tokens=350,
        text_format=CVReview,
    )
    return response.output_parsed


def save_review(rows):
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    output = pd.DataFrame(rows, columns=["NMI", "classified_tier", "cv_judgement", "cv_reason"])
    output.to_csv(OUTPUT_CSV, index=False)
    output.to_excel(OUTPUT_XLSX, index=False)
    return output


def main():
    args = parse_args()
    from openai import OpenAI

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    energy = load_energy()
    classified = selected_rows(load_classification(args.classification_csv), args.nmi, args.limit)
    client = OpenAI(api_key=read_api_key())

    rows = []
    for index, row in classified.iterrows():
        nmi = str(row["NMI"])
        tier = str(row["forecastability_tier"])
        print(f"[{index + 1}/{len(classified)}] Reviewing {nmi}: {tier}")

        image_paths = generate_review_images(energy, row)
        review = review_nmi(client, args.model, row, image_paths)

        rows.append({
            "NMI": nmi,
            "classified_tier": tier,
            "cv_judgement": review.classification_reasonable,
            "cv_reason": review.reason,
        })

    output = save_review(rows)
    print("Saved CSV:", OUTPUT_CSV)
    print("Saved Excel:", OUTPUT_XLSX)
    print("Rows:", len(output))


if __name__ == "__main__":
    main()
