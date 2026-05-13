from __future__ import annotations

from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd


warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "Datasets"
EDA_DIR = PROJECT_ROOT / "EDA_Tasks"
OUTPUT_DIR = EDA_DIR / "NMI_score_classification_results"
OUTPUT_DIR.mkdir(exist_ok=True)

ENERGY_CSV = DATA_DIR / "LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv"
ARCHIBUS_XLSX = DATA_DIR / "Archibus Extract_Buildings_May 2026.xlsx"
LMS_NMI_MAP_XLSX = DATA_DIR / "LMS Serial to NMI Map.xlsx"
PARKVILLE_SUBSTATION_XLSX = DATA_DIR / "Parkville Substation Mapping.xlsx"
BUILDING_NMI_JSON = EDA_DIR / "4" / "building_nmi_mapping.json"

DROP_NMIS = {"6102507141", "VAAA003225"}
MIN_ACTIVE_DAYS_FOR_BACKTEST = 365
MIN_VALIDATION_POINTS = 48 * 30


def normalise_code(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def unique_join(values, sep="; "):
    clean = sorted({str(v).strip() for v in values if pd.notna(v) and str(v).strip() != ""})
    return sep.join(clean) if clean else pd.NA


def clean_building_type(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    bad_values = {"", ".N/A", "N/A", "NA", "nan", "none", "c"}
    if text in bad_values or text[:1].isdigit():
        return pd.NA
    return text


def safe_divide(numerator, denominator):
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


def wape(y_true, y_pred):
    valid = y_true.notna() & y_pred.notna()
    y_true = y_true[valid]
    y_pred = y_pred[valid]
    denominator = y_true.abs().sum()
    if len(y_true) == 0 or denominator == 0:
        return np.nan
    return (y_true - y_pred).abs().sum() / denominator


def longest_true_run(mask):
    if mask.empty or not mask.any():
        return 0
    groups = mask.ne(mask.shift()).cumsum()
    return int(mask.groupby(groups).sum().max())


def iqr_outlier_rate(values):
    values = values.dropna()
    if len(values) < 10:
        return np.nan
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return ((values < lower) | (values > upper)).mean()


def lag_corr(values, lag):
    values = values.astype(float)
    if values.notna().sum() <= lag + 10:
        return np.nan
    return values.corr(values.shift(lag))


def cycle_strength(active_df, value_col, group_cols):
    values = active_df[value_col].dropna()
    total_var = values.var()
    if len(values) < 10 or pd.isna(total_var) or total_var == 0:
        return np.nan
    grouped_mean = active_df.groupby(group_cols)[value_col].mean()
    return safe_divide(grouped_mean.var(), total_var)


def percentile_score(series, higher_is_better):
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    score = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.dropna()

    if valid.empty:
        return score
    if valid.nunique() == 1:
        score.loc[valid.index] = 0.5
        return score

    ranks = valid.rank(method="average", ascending=True, pct=True)
    if higher_is_better:
        score.loc[valid.index] = ranks
    else:
        score.loc[valid.index] = 1 - ranks + 1 / len(valid)
    return score.clip(0, 1)


def minmax_score(series, higher_is_better):
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


def threshold_score(value, thresholds):
    if pd.isna(value):
        return np.nan
    for upper, score in thresholds:
        if value <= upper:
            return score
    return thresholds[-1][1]


def missing_rate_score(rate):
    return threshold_score(rate, [
        (0.001, 1.00),
        (0.010, 0.90),
        (0.050, 0.75),
        (0.100, 0.50),
        (0.200, 0.25),
        (np.inf, 0.05),
    ])


def zero_rate_score(rate):
    return threshold_score(rate, [
        (0.010, 1.00),
        (0.050, 0.90),
        (0.100, 0.75),
        (0.300, 0.50),
        (0.500, 0.25),
        (np.inf, 0.05),
    ])


def zero_run_score(hours):
    return threshold_score(hours, [
        (12, 1.00),
        (24, 0.90),
        (72, 0.70),
        (168, 0.40),
        (np.inf, 0.10),
    ])


def outlier_rate_score(rate):
    return threshold_score(rate, [
        (0.005, 1.00),
        (0.010, 0.90),
        (0.030, 0.75),
        (0.050, 0.50),
        (0.100, 0.25),
        (np.inf, 0.05),
    ])


def baseline_backtest(active_df, value_col):
    df_bt = active_df[["date", value_col]].dropna().copy().sort_values("date")
    result = {
        "validation_start": pd.NaT,
        "validation_points": 0,
        "validation_months": 0,
        "WAPE_lag48": np.nan,
        "WAPE_lag336": np.nan,
        "WAPE_calendar": np.nan,
        "best_baseline_type": pd.NA,
        "best_baseline_WAPE": np.nan,
    }

    if df_bt.empty:
        return result

    active_days = (df_bt["date"].max() - df_bt["date"].min()).days
    if active_days < MIN_ACTIVE_DAYS_FOR_BACKTEST:
        return result

    validation_start = df_bt["date"].min() + pd.Timedelta(days=MIN_ACTIVE_DAYS_FOR_BACKTEST)
    result["validation_start"] = validation_start

    y = df_bt[value_col].astype(float)
    pred_lag48 = y.shift(48)
    pred_lag336 = y.shift(336)

    df_bt["dow"] = df_bt["date"].dt.dayofweek
    df_bt["tod"] = df_bt["date"].dt.strftime("%H:%M")
    pred_calendar = y.groupby([df_bt["dow"], df_bt["tod"]]).transform(
        lambda s: s.shift(1).expanding(min_periods=4).mean()
    )

    validation_mask = df_bt["date"] >= validation_start
    result["validation_points"] = int(validation_mask.sum())
    result["validation_months"] = int(df_bt.loc[validation_mask, "date"].dt.to_period("M").nunique())

    if result["validation_points"] < MIN_VALIDATION_POINTS:
        return result

    y_valid = y[validation_mask]
    result["WAPE_lag48"] = wape(y_valid, pred_lag48[validation_mask])
    result["WAPE_lag336"] = wape(y_valid, pred_lag336[validation_mask])
    result["WAPE_calendar"] = wape(y_valid, pred_calendar[validation_mask])

    baseline_errors = {
        "lag48": result["WAPE_lag48"],
        "lag336": result["WAPE_lag336"],
        "calendar": result["WAPE_calendar"],
    }
    baseline_errors = {k: v for k, v in baseline_errors.items() if pd.notna(v)}

    if baseline_errors:
        best_type = min(baseline_errors, key=baseline_errors.get)
        result["best_baseline_type"] = best_type
        result["best_baseline_WAPE"] = baseline_errors[best_type]

    return result


def load_energy():
    energy_raw = pd.read_csv(ENERGY_CSV)
    energy_raw["date"] = pd.to_datetime(energy_raw["date"])
    energy_raw = energy_raw.sort_values("date").reset_index(drop=True)

    energy = energy_raw.copy()
    energy.columns = [
        col.replace(" consumption", "") if col != "date" else col
        for col in energy.columns
    ]
    energy = energy.drop(columns=[nmi for nmi in DROP_NMIS if nmi in energy.columns])

    nmi_cols = [col for col in energy.columns if col != "date"]
    latest_timestamp = energy["date"].max()
    return energy, nmi_cols, latest_timestamp


def load_nmi_metadata(nmi_cols):
    if ARCHIBUS_XLSX.exists():
        archibus = pd.read_excel(ARCHIBUS_XLSX, header=2)
        archibus = archibus.rename(columns={
            "Building Code": "building_code",
            "Building Name": "building_name",
            "Building Type": "building_type",
            "Campus Code": "campus_code",
            "Longitude": "longitude",
            "Latitude": "latitude",
        })
        archibus["building_code"] = archibus["building_code"].map(normalise_code)
        archibus["building_type"] = archibus["building_type"].map(clean_building_type)
        archibus_lookup = archibus[[
            "building_code", "building_name", "building_type", "campus_code", "longitude", "latitude"
        ]].drop_duplicates()
    else:
        archibus_lookup = pd.DataFrame(columns=[
            "building_code", "building_name", "building_type", "campus_code", "longitude", "latitude"
        ])

    mapping_rows = []

    if BUILDING_NMI_JSON.exists():
        with BUILDING_NMI_JSON.open(encoding="utf-8") as f:
            building_mapping = json.load(f)

        for section, entries in building_mapping.items():
            if section == "unmapped_nmis":
                for nmi in entries:
                    mapping_rows.append({
                        "NMI": normalise_code(nmi),
                        "building_code": pd.NA,
                        "mapping_source": "building_nmi_mapping_json",
                        "mapping_section": "unmapped_nmis",
                    })
            else:
                for building_code, nmis in entries.items():
                    for nmi in nmis:
                        mapping_rows.append({
                            "NMI": normalise_code(nmi),
                            "building_code": normalise_code(building_code),
                            "mapping_source": "building_nmi_mapping_json",
                            "mapping_section": section,
                        })

    if LMS_NMI_MAP_XLSX.exists():
        lms_map = pd.read_excel(LMS_NMI_MAP_XLSX)
        lms_map["NMI"] = lms_map["NMI"].map(normalise_code)
        lms_map["LocationCode"] = lms_map["LocationCode"].map(normalise_code)

        for _, row in lms_map.iterrows():
            location = row.get("LocationCode")
            building_code = normalise_code(location.split(";")[-1]) if isinstance(location, str) and ";" in location else pd.NA
            mapping_rows.append({
                "NMI": row["NMI"],
                "building_code": building_code,
                "mapping_source": "LMS Serial to NMI Map",
                "mapping_section": "location_code",
            })

    if PARKVILLE_SUBSTATION_XLSX.exists():
        parkville_raw = pd.read_excel(PARKVILLE_SUBSTATION_XLSX, sheet_name="Parkville", header=None)
        parkville = parkville_raw.iloc[5:, 1:6].copy()
        parkville.columns = ["substation", "NMI", "meter_split", "building_code", "building_name_from_substation"]
        parkville[["substation", "NMI", "meter_split"]] = parkville[["substation", "NMI", "meter_split"]].ffill()
        parkville["NMI"] = parkville["NMI"].map(normalise_code)
        parkville["building_code"] = parkville["building_code"].map(normalise_code)
        parkville = parkville.dropna(subset=["NMI"])

        for _, row in parkville.iterrows():
            mapping_rows.append({
                "NMI": row["NMI"],
                "building_code": row["building_code"],
                "mapping_source": "Parkville Substation Mapping",
                "mapping_section": "substation_shared",
            })

    nmi_building_long = pd.DataFrame(mapping_rows).drop_duplicates()
    nmi_building_long = nmi_building_long[nmi_building_long["NMI"].notna()]
    nmi_building_enriched = nmi_building_long.merge(archibus_lookup, on="building_code", how="left")

    nmi_metadata = (
        nmi_building_enriched
        .groupby("NMI")
        .agg(
            building_codes=("building_code", unique_join),
            building_names=("building_name", unique_join),
            building_type=("building_type", unique_join),
            campus_codes=("campus_code", unique_join),
            mapping_sources=("mapping_source", unique_join),
        )
        .reset_index()
    )

    quality = (
        nmi_building_enriched.groupby("NMI")
        .apply(mapping_quality_for_group)
        .rename("mapping_quality")
        .reset_index()
    )
    nmi_metadata = nmi_metadata.merge(quality, on="NMI", how="left")

    nmi_metadata["building_type_group"] = nmi_metadata["building_type"].apply(building_type_group)
    nmi_metadata["building_type_count"] = nmi_metadata["building_type"].apply(
        lambda x: 0 if pd.isna(x) else len({v.strip() for v in str(x).split(";") if v.strip()})
    )

    nmi_metadata = pd.DataFrame({"NMI": nmi_cols}).merge(nmi_metadata, on="NMI", how="left")
    nmi_metadata["building_type"] = nmi_metadata["building_type"].fillna("Unknown")
    nmi_metadata["building_type_group"] = nmi_metadata["building_type_group"].fillna("Unknown")
    nmi_metadata["mapping_quality"] = nmi_metadata["mapping_quality"].fillna("unknown")
    return nmi_metadata


def mapping_quality_for_group(group):
    sections = set(group["mapping_section"].dropna().astype(str))
    building_codes = set(group["building_code"].dropna().astype(str))

    if "unmapped_nmis" in sections and not building_codes:
        return "unmapped"
    if "many_to_many" in sections:
        return "many_to_many"
    if "many_to_one" in sections:
        return "many_to_one"
    if "substation_shared" in sections and len(building_codes) > 1:
        return "substation_shared_multi_building"
    if len(building_codes) == 1:
        return "one_building_mapped"
    if len(building_codes) > 1:
        return "multi_building_mapped"
    return "unknown"


def building_type_group(types_text):
    if pd.isna(types_text) or str(types_text).strip() == "":
        return "Unknown"
    types = [x.strip() for x in str(types_text).split(";") if x.strip()]
    if len(set(types)) <= 1:
        return "Single"
    return "Mixed"


def calculate_metrics(energy, nmi_cols, latest_timestamp):
    metric_rows = []

    for nmi in nmi_cols:
        nmi_df = energy[["date", nmi]].copy()
        values_all = pd.to_numeric(nmi_df[nmi], errors="coerce")
        nonzero_mask = values_all.fillna(0).ne(0)

        active_start = nmi_df.loc[nonzero_mask, "date"].min() if nonzero_mask.any() else pd.NaT
        active_end = nmi_df.loc[nonzero_mask, "date"].max() if nonzero_mask.any() else pd.NaT
        active_df = nmi_df[nmi_df["date"].between(active_start, active_end)].copy()

        active_values = pd.to_numeric(active_df[nmi], errors="coerce")
        active_count = len(active_df)
        active_days = (active_end - active_start).days if pd.notna(active_start) else 0
        active_years = active_days / 365.25 if active_days else 0

        missing_rate = active_values.isna().mean() if active_count else np.nan
        zero_rate = active_values.fillna(0).eq(0).mean() if active_count else np.nan
        negative_count = int(active_values.lt(0).sum()) if active_count else 0
        longest_zero_run = longest_true_run(active_values.fillna(np.nan).eq(0)) if active_count else 0
        longest_zero_run_ratio = safe_divide(longest_zero_run, active_count)
        outlier_rate = iqr_outlier_rate(active_values)

        recent_12m_start = latest_timestamp - pd.DateOffset(months=12)
        recent_24m_start = latest_timestamp - pd.DateOffset(months=24)
        recent_12m = nmi_df[nmi_df["date"].between(recent_12m_start, latest_timestamp)][nmi]
        recent_24m = nmi_df[nmi_df["date"].between(recent_24m_start, latest_timestamp)][nmi]
        recent_coverage_12m = recent_12m.fillna(0).ne(0).mean()
        recent_coverage_24m = recent_24m.fillna(0).ne(0).mean()

        if pd.isna(zero_rate) or active_start == active_end:
            status = "Dead"
        elif zero_rate < 0.01:
            status = "Active"
        elif zero_rate < 0.10:
            status = "Mostly Active"
        elif zero_rate < 0.50:
            status = "Intermittent"
        elif zero_rate < 1.00:
            status = "Mostly inactive"
        else:
            status = "Dead"

        lag_1 = lag_corr(active_values, 1)
        lag_2 = lag_corr(active_values, 2)
        lag_48 = lag_corr(active_values, 48)
        lag_336 = lag_corr(active_values, 336)

        active_df = active_df.assign(
            value=active_values.values,
            half_hour=active_df["date"].dt.strftime("%H:%M"),
            dayofweek=active_df["date"].dt.dayofweek,
        )
        daily_cycle_strength = cycle_strength(active_df, "value", ["half_hour"])
        weekly_pattern_strength = cycle_strength(active_df, "value", ["dayofweek", "half_hour"])

        daily_total = active_df.set_index("date")["value"].resample("D").sum(min_count=1).dropna()

        if len(daily_total) >= 30 and daily_total.mean() != 0:
            x = np.arange(len(daily_total))
            slope = np.polyfit(x, daily_total.values, 1)[0]
            trend_strength = abs(slope) / abs(daily_total.mean())
            rolling_mean = daily_total.rolling(window=30, min_periods=15).mean()
            structural_break = rolling_mean.diff().abs().max() / abs(daily_total.mean())
        else:
            trend_strength = np.nan
            structural_break = np.nan

        yearly_mean = daily_total.groupby(daily_total.index.year).mean()
        yearly_variation = safe_divide(yearly_mean.std(), yearly_mean.mean()) if len(yearly_mean) >= 2 else np.nan

        monthly_mean = daily_total.groupby(daily_total.index.month).mean()
        seasonality_strength = (
            safe_divide(monthly_mean.var(), daily_total.var())
            if len(monthly_mean) >= 2 and daily_total.var() != 0 else np.nan
        )

        bt_input = active_df[["date", "value"]].rename(columns={"value": nmi})
        bt = baseline_backtest(bt_input, nmi)

        metric_rows.append({
            "NMI": nmi,
            "active_start": active_start,
            "active_end": active_end,
            "active_years": active_years,
            "active_readings": active_count,
            "status": status,
            "missing_rate": missing_rate,
            "zero_rate": zero_rate,
            "negative_count": negative_count,
            "longest_zero_run": longest_zero_run,
            "longest_zero_run_hours": longest_zero_run * 0.5,
            "longest_zero_run_ratio": longest_zero_run_ratio,
            "outlier_rate": outlier_rate,
            "recent_coverage_12m": recent_coverage_12m,
            "recent_coverage_24m": recent_coverage_24m,
            "lag_1_corr": lag_1,
            "lag_2_corr": lag_2,
            "lag_48_corr": lag_48,
            "lag_336_corr": lag_336,
            "daily_cycle_strength": daily_cycle_strength,
            "weekly_pattern_strength": weekly_pattern_strength,
            "seasonality_strength": seasonality_strength,
            "trend_strength": trend_strength,
            "yearly_variation": yearly_variation,
            "structural_break_score": structural_break,
            **bt,
        })

    return pd.DataFrame(metric_rows)


def score_summary(summary):
    scored = summary.copy()

    scored["performance_score"] = minmax_score(scored["best_baseline_WAPE"], higher_is_better=False)

    scored["missing_score"] = scored["missing_rate"].apply(missing_rate_score)
    scored["zero_score"] = scored["zero_rate"].apply(zero_rate_score)
    scored["zero_run_score"] = scored["longest_zero_run_hours"].apply(zero_run_score)
    scored["outlier_score"] = scored["outlier_rate"].apply(outlier_rate_score)
    scored["data_quality_score"] = scored[[
        "missing_score", "zero_score", "zero_run_score", "outlier_score"
    ]].mean(axis=1, skipna=True)

    scored["active_years_score"] = percentile_score(scored["active_years"], higher_is_better=True)
    scored["recent_coverage_score"] = percentile_score(scored["recent_coverage_24m"], higher_is_better=True)
    scored["validation_months_score"] = percentile_score(scored["validation_months"], higher_is_better=True)
    scored["history_score"] = scored[[
        "active_years_score", "recent_coverage_score", "validation_months_score"
    ]].mean(axis=1, skipna=True)

    scored["lag_48_score"] = percentile_score(scored["lag_48_corr"].abs(), higher_is_better=True)
    scored["lag_336_score"] = percentile_score(scored["lag_336_corr"].abs(), higher_is_better=True)
    scored["daily_cycle_score"] = percentile_score(scored["daily_cycle_strength"], higher_is_better=True)
    scored["weekly_pattern_score"] = percentile_score(scored["weekly_pattern_strength"], higher_is_better=True)
    scored["seasonality_score"] = percentile_score(scored["seasonality_strength"], higher_is_better=True)
    scored["temporal_pattern_score"] = scored[[
        "lag_48_score", "lag_336_score", "daily_cycle_score",
        "weekly_pattern_score", "seasonality_score"
    ]].mean(axis=1, skipna=True)

    scored["trend_score"] = percentile_score(scored["trend_strength"], higher_is_better=False)
    scored["yearly_variation_score"] = percentile_score(scored["yearly_variation"], higher_is_better=False)
    scored["structural_break_score_scaled"] = percentile_score(scored["structural_break_score"], higher_is_better=False)
    scored["stability_score"] = scored[[
        "trend_score", "yearly_variation_score", "structural_break_score_scaled"
    ]].mean(axis=1, skipna=True)

    mapping_score_map = {
        "one_building_mapped": 1.00,
        "many_to_one": 0.80,
        "multi_building_mapped": 0.65,
        "substation_shared_multi_building": 0.55,
        "many_to_many": 0.45,
        "unknown": 0.30,
        "unmapped": 0.20,
    }
    scored["mapping_score"] = scored["mapping_quality"].map(mapping_score_map).fillna(0.30)

    score_weights = {
        "performance_score": 0.35,
        "data_quality_score": 0.20,
        "history_score": 0.15,
        "temporal_pattern_score": 0.15,
        "stability_score": 0.10,
        "mapping_score": 0.05,
    }
    scored["forecastability_score"] = scored.apply(lambda row: weighted_score(row, score_weights), axis=1)
    scored["score_confidence"] = scored.apply(
        lambda row: sum(weight for col, weight in score_weights.items() if pd.notna(row.get(col))),
        axis=1,
    )
    return scored


def weighted_score(row, weights):
    numerator = 0.0
    denominator = 0.0
    for col, weight in weights.items():
        value = row.get(col)
        if pd.notna(value):
            numerator += weight * value
            denominator += weight
    return safe_divide(numerator, denominator)


def classify(scored):
    classified = scored.copy()
    classified["forecastability_tier"] = pd.NA

    exclude_mask = (
        classified["status"].isin(["Dead", "Mostly inactive"])
        | (classified["active_years"] < 0.25)
        | (classified["zero_rate"] >= 0.80)
    )
    classified.loc[exclude_mask, "forecastability_tier"] = "Exclude / Needs Review"

    short_history_mask = (
        classified["forecastability_tier"].isna()
        & (
            (classified["active_years"] < 1.0)
            | (classified["validation_months"].fillna(0) < 3)
            | (classified["best_baseline_WAPE"].isna())
        )
    )
    classified.loc[short_history_mask, "forecastability_tier"] = "Tier C - Short-history candidate"

    eligible_mask = classified["forecastability_tier"].isna() & classified["forecastability_score"].notna()
    eligible_scores = classified.loc[eligible_mask, "forecastability_score"]

    if len(eligible_scores) >= 4:
        q25 = eligible_scores.quantile(0.25)
        q75 = eligible_scores.quantile(0.75)
        classified.loc[
            eligible_mask & (classified["forecastability_score"] >= q75),
            "forecastability_tier",
        ] = "Tier A - Strong forecasting candidate"
        classified.loc[
            eligible_mask & (classified["forecastability_score"] <= q25),
            "forecastability_tier",
        ] = "Tier D - Difficult forecasting candidate"
        classified.loc[
            classified["forecastability_tier"].isna() & eligible_mask,
            "forecastability_tier",
        ] = "Tier B - Usable with caution"
    else:
        classified.loc[eligible_mask, "forecastability_tier"] = "Tier B - Usable with caution"

    structural_break_q75 = classified["structural_break_score"].quantile(0.75)
    classified["forecastability_tier"] = classified["forecastability_tier"].fillna("Exclude / Needs Review")
    classified["recommended_model_strategy"] = classified["forecastability_tier"].apply(recommended_strategy)
    classified["reason"] = classified.apply(lambda row: reason_text(row, structural_break_q75), axis=1)
    return classified


def recommended_strategy(tier):
    if tier.startswith("Tier A"):
        return "Individual model; suitable for regular forecasting and benchmark model comparison"
    if tier.startswith("Tier B"):
        return "Individual model with caution; consider recent-window training, changepoint features, and anomaly handling"
    if tier.startswith("Tier C"):
        return "Pooled/global model; borrow strength from similar NMIs/building types and calendar/weather features"
    if tier.startswith("Tier D"):
        return "Low priority for individual model; consider aggregation or operational/data-quality review"
    return "Exclude from individual forecasting until mapping/data quality is reviewed"


def reason_text(row, structural_break_q75):
    reasons = []

    if row["active_years"] < 1:
        reasons.append("short active history")
    elif row["active_years"] >= 5:
        reasons.append("long active history")

    if pd.notna(row["best_baseline_WAPE"]):
        if row["performance_score"] >= 0.75:
            reasons.append("low baseline WAPE")
        elif row["performance_score"] <= 0.25:
            reasons.append("high baseline WAPE")
    else:
        reasons.append("insufficient backtesting history")

    if pd.notna(row["zero_rate"]):
        if row["zero_rate"] >= 0.50:
            reasons.append("high zero rate")
        elif row["zero_rate"] < 0.01:
            reasons.append("very low zero rate")

    if pd.notna(row["longest_zero_run_hours"]) and row["longest_zero_run_hours"] >= 24:
        reasons.append("long zero run")

    if pd.notna(row["lag_48_corr"]) or pd.notna(row["lag_336_corr"]):
        max_lag_corr = np.nanmax([abs(row.get("lag_48_corr", np.nan)), abs(row.get("lag_336_corr", np.nan))])
        if pd.notna(max_lag_corr) and max_lag_corr >= 0.80:
            reasons.append("strong daily/weekly temporal dependency")
        elif pd.notna(max_lag_corr) and max_lag_corr < 0.40:
            reasons.append("weak daily/weekly temporal dependency")

    if pd.notna(row["structural_break_score"]) and row["structural_break_score"] >= structural_break_q75:
        reasons.append("large rolling-mean shift")

    if row.get("building_type_group") == "Mixed":
        reasons.append("multiple building types mapped")
    if row.get("mapping_quality") in {"unknown", "unmapped", "many_to_many"}:
        reasons.append("mapping quality needs review")

    if not reasons:
        reasons.append("balanced diagnostic profile")

    return "; ".join(reasons)


def export_final_table(classified):
    final_columns = [
        "NMI", "building_codes", "building_names", "building_type", "building_type_group",
        "building_type_count", "campus_codes", "mapping_quality", "mapping_sources",
        "active_start", "active_end", "active_years", "active_readings", "status",
        "recent_coverage_12m", "recent_coverage_24m",
        "missing_rate", "zero_rate", "negative_count", "longest_zero_run",
        "longest_zero_run_hours", "longest_zero_run_ratio", "outlier_rate",
        "lag_1_corr", "lag_2_corr", "lag_48_corr", "lag_336_corr",
        "daily_cycle_strength", "weekly_pattern_strength", "seasonality_strength",
        "trend_strength", "yearly_variation", "structural_break_score",
        "validation_start", "validation_points", "validation_months",
        "WAPE_lag48", "WAPE_lag336", "WAPE_calendar",
        "best_baseline_type", "best_baseline_WAPE",
        "performance_score", "data_quality_score", "history_score",
        "temporal_pattern_score", "stability_score", "mapping_score",
        "forecastability_score", "score_confidence",
        "forecastability_tier", "recommended_model_strategy", "reason",
    ]
    final_table = classified[final_columns].sort_values(
        ["forecastability_tier", "forecastability_score"],
        ascending=[True, False],
    ).reset_index(drop=True)

    csv_output = OUTPUT_DIR / "NMI_forecastability_summary_threshold.csv"
    xlsx_output = OUTPUT_DIR / "NMI_forecastability_summary_threshold.xlsx"
    final_table.to_csv(csv_output, index=False)
    final_table.to_excel(xlsx_output, index=False)

    print("Saved CSV:", csv_output)
    print("Saved Excel:", xlsx_output)
    print("Final table shape:", final_table.shape)
    print("\nForecastability tier counts:")
    print(final_table["forecastability_tier"].value_counts())
    print("\nBuilding type group by tier:")
    print(pd.crosstab(final_table["forecastability_tier"], final_table["building_type_group"], margins=True))


def main():
    energy, nmi_cols, latest_timestamp = load_energy()
    nmi_metadata = load_nmi_metadata(nmi_cols)
    metrics = calculate_metrics(energy, nmi_cols, latest_timestamp)

    summary = metrics.merge(nmi_metadata, on="NMI", how="left")
    metadata_cols = [
        "building_codes", "building_names", "building_type", "building_type_group",
        "campus_codes", "mapping_sources", "mapping_quality",
    ]
    summary[metadata_cols] = summary[metadata_cols].fillna("Unknown")

    scored = score_summary(summary)
    classified = classify(scored)
    export_final_table(classified)


if __name__ == "__main__":
    main()
