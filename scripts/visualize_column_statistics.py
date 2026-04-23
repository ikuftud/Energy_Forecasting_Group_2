import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
parser.add_argument("output_png", type=Path)
args = parser.parse_args()

df = pd.read_csv(args.csv, index_col=0)
fig, axes = plt.subplots(2, 3, figsize=(15, 8))

for ax, stat in zip(axes.flat, ["median", "max", "min", "mean", "std"]):
    ax.hist(df[stat], bins=30, edgecolor="black")
    ax.set_title(stat)

axes.flat[5].scatter(df["mean"], df["std"], s=12)
axes.flat[5].set_title("mean vs std")
axes.flat[5].set_xlabel("mean")
axes.flat[5].set_ylabel("std")

fig.tight_layout()
fig.savefig(args.output_png, dpi=200)
