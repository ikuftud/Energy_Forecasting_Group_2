from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING_JSON = ROOT / "scripts" / "building_nmi_mapping.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge an NMI-level wide CSV into grouped building-level columns.")
    parser.add_argument("input_csv", type=Path, help="Path to the NMI-level wide CSV file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to the merged output CSV. Defaults to the same folder as the input file.",
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=DEFAULT_MAPPING_JSON,
        help="Path to the building/NMI mapping JSON.",
    )
    return parser.parse_args()


def load_mapping_json(path: Path) -> dict[str, object]:
    with path.open() as f:
        mapping = json.load(f)

    required_keys = ["building_to_nmis", "many_to_one", "many_to_many", "unmapped_nmis"]
    if sorted(mapping.keys()) != sorted(required_keys):
        raise ValueError(f"Mapping JSON must contain exactly these keys: {required_keys}")

    for key in ["building_to_nmis", "many_to_one", "many_to_many"]:
        if not isinstance(mapping[key], dict):
            raise ValueError(f"Mapping JSON field '{key}' must be a dictionary.")

    if not isinstance(mapping["unmapped_nmis"], list):
        raise ValueError("Mapping JSON field 'unmapped_nmis' must be a list.")

    return mapping


def get_input_nmis(columns: list[str]) -> list[str]:
    if "date" not in columns:
        raise ValueError("Input CSV must contain a 'date' column.")

    nmi_columns = [column for column in columns if column != "date"]
    if any(not column.endswith(" consumption") for column in nmi_columns):
        raise ValueError("Every non-date input column must end with ' consumption'.")

    input_nmis = [column.removesuffix(" consumption") for column in nmi_columns]
    if len(input_nmis) != len(set(input_nmis)):
        raise ValueError("Input CSV contains duplicate NMI columns.")

    return input_nmis


def build_output_specs(mapping: dict[str, object]) -> tuple[list[tuple[str, list[str]]], list[str]]:
    output_specs: list[tuple[str, list[str]]] = []
    output_columns: list[str] = []
    all_json_nmis: list[str] = []

    for section_name in ["building_to_nmis", "many_to_one", "many_to_many"]:
        section = mapping[section_name]
        for output_column, nmis in section.items():
            if not isinstance(output_column, str):
                raise ValueError(f"Output column in section '{section_name}' must be a string.")
            if not isinstance(nmis, list) or not nmis:
                raise ValueError(f"Section '{section_name}' entry '{output_column}' must map to a non-empty list of NMIs.")
            if any(not isinstance(nmi, str) for nmi in nmis):
                raise ValueError(f"Section '{section_name}' entry '{output_column}' must only contain string NMIs.")

            output_specs.append((output_column, nmis))
            output_columns.append(output_column)
            all_json_nmis.extend(nmis)

    for nmi in mapping["unmapped_nmis"]:
        if not isinstance(nmi, str):
            raise ValueError("Every value in 'unmapped_nmis' must be a string.")
        output_specs.append((nmi, [nmi]))
        output_columns.append(nmi)
        all_json_nmis.append(nmi)

    if len(output_columns) != len(set(output_columns)):
        raise ValueError("Mapping JSON produces duplicate output column names.")

    if len(all_json_nmis) != len(set(all_json_nmis)):
        raise ValueError("Mapping JSON contains duplicate NMIs across sections.")

    return output_specs, all_json_nmis


def validate_coverage(input_nmis: list[str], all_json_nmis: list[str]) -> None:
    input_nmi_set = set(input_nmis)
    json_nmi_set = set(all_json_nmis)

    if input_nmi_set != json_nmi_set:
        missing_from_json = sorted(input_nmi_set - json_nmi_set)
        extra_in_json = sorted(json_nmi_set - input_nmi_set)
        raise ValueError(
            "Input CSV and mapping JSON do not cover the same NMI set. "
            f"Missing from JSON: {missing_from_json}. Extra in JSON: {extra_in_json}."
        )


def merge_csv(input_csv: Path, mapping_json: Path, output_csv: Path) -> None:
    mapping = load_mapping_json(mapping_json)
    input_header = pd.read_csv(input_csv, nrows=0)
    input_nmis = get_input_nmis(list(input_header.columns))
    output_specs, all_json_nmis = build_output_specs(mapping)
    validate_coverage(input_nmis, all_json_nmis)

    df = pd.read_csv(input_csv)
    result = pd.DataFrame({"date": df["date"]})

    for output_column, nmis in output_specs:
        source_columns = [f"{nmi} consumption" for nmi in nmis]
        result[output_column] = df[source_columns].sum(axis=1)

    result.to_csv(output_csv, index=False)


def main() -> None:
    args = parse_args()
    output_path = args.output
    if output_path is None:
        output_path = args.input_csv.with_name(f"{args.input_csv.stem}_merged_by_building.csv")

    merge_csv(args.input_csv, args.mapping_json, output_path)
    print(f"Saved merged CSV to {output_path}")


if __name__ == "__main__":
    main()
