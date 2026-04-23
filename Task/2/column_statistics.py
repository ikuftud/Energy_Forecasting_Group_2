import argparse
from pathlib import Path

import pandas as pd


parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
parser.add_argument("output_csv", type=Path)
args = parser.parse_args()

df = pd.read_csv(args.csv).iloc[:, 1:]
df.agg(["median", "max", "min", "mean", "std"]).T.to_csv(args.output_csv)
