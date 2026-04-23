from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate a half-hour wide CSV to 1-hour or 1-day intervals.")
    parser.add_argument("input_csv", type=Path, help="Path to the input CSV file.")
    parser.add_argument("period", choices=["1h", "1d"], help="Aggregation period.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to the output CSV file. Defaults to the same folder as the input file.",
    )
    return parser.parse_args()


def build_output_path(input_csv: Path, period: str, output: Path | None) -> Path:
    if output is not None:
        return output
    return input_csv.with_name(f"{input_csv.stem}_{period}.csv")


def aggregate_csv(input_csv: Path, period: str, output_csv: Path) -> None:
    df = pd.read_csv(input_csv)
    if "date" not in df.columns:
        raise ValueError("Input CSV must contain a 'date' column.")

    value_columns = [column for column in df.columns if column != "date"]
    if not value_columns:
        raise ValueError("Input CSV must contain at least one value column besides 'date'.")

    if not all(pd.api.types.is_numeric_dtype(df[column]) for column in value_columns):
        raise ValueError("All non-date columns must be numeric.")

    floor_rule = "h" if period == "1h" else "D"

    result = (
        df.assign(date=pd.to_datetime(df["date"]).dt.floor(floor_rule))
        .groupby("date", as_index=False)[value_columns]
        .sum()
    )
    result["date"] = result["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    result.to_csv(output_csv, index=False)


def main() -> None:
    args = parse_args()
    output_csv = build_output_path(args.input_csv, args.period, args.output)
    aggregate_csv(args.input_csv, args.period, output_csv)
    print(f"Saved aggregated CSV to {output_csv}")


if __name__ == "__main__":
    main()
