import argparse
import json
from pathlib import Path

import pandas as pd


parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
parser.add_argument("output_json", type=Path)
args = parser.parse_args()

df = pd.read_csv(args.csv)
result = ((df.iloc[:, 1:] != 0)[::-1].idxmax() + 1).to_dict()
args.output_json.write_text(json.dumps(result))
