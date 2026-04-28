from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SITE_TOTAL_COLUMN = "site_total"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge all value columns in a CSV into one site-level column.")
    parser.add_argument("input_csv", type=Path, help="Path to the CSV file to process.")
    parser.add_argument("output_csv", type=Path, help="Path to save the merged output CSV.")
    return parser.parse_args()


def get_value_columns(columns: list[str]) -> list[str]:
    if "date" not in columns:
        raise ValueError("Input CSV must contain a 'date' column.")

    value_columns = [column for column in columns if column != "date"]
    if not value_columns:
        raise ValueError("Input CSV must contain at least one value column besides 'date'.")

    return value_columns


def merge_csv(input_csv: Path, output_csv: Path) -> None:
    df = pd.read_csv(input_csv)
    value_columns = get_value_columns(list(df.columns))

    values = df[value_columns].apply(pd.to_numeric, errors="raise")
    result = pd.DataFrame(
        {
            "date": df["date"],
            SITE_TOTAL_COLUMN: values.sum(axis=1),
        }
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False)


def main() -> None:
    args = parse_args()
    merge_csv(args.input_csv, args.output_csv)
    print(f"Saved site-level CSV to {args.output_csv}")


if __name__ == "__main__":
    main()
