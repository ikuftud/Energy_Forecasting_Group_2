# Repository guide

This change groups the files already tracked in this repository. It does not upload the separate local Final_Submission package, raw datasets or newly generated model results.

## Locations

| Location | Contents |
|---|---|
| EDA_Tasks | Existing task notebooks, NMI classification and mapping work; internal paths are retained |
| EDA_Tasks/Exploration | The earlier MAST90106 EDA.ipynb and Project data exploration.ipynb |
| Model/LSTM | lstm.ipynb, lstm_updated.ipynb and lstm_updated_solar.ipynb |
| nmi_agent_project | Existing NMI scoring, tuning, review and final-test tools; package structure is unchanged |
| scripts | Existing date-aggregation and last-nonzero utilities |
| Documents | project-brief-378.pdf |

The existing README is readme.md (lowercase).

## LSTM versions

The three notebooks contain different code and are retained separately:

- lstm.ipynb uses nmi_daily_preprocessing.csv and the earlier 30-day lookback.
- lstm_updated.ipynb uses final_nmi_model_input.csv, a 14-day lookback and expanding-fold tuning.
- lstm_updated_solar.ipynb extends the updated version with solar inputs.

These names do not establish which experiment should be treated as the final submitted model.

## Working directories and inputs

File organization does not change the model calculations or make the notebooks portable automatically.

- The two notebooks in EDA_Tasks/Exploration still read paths beginning with Datasets/ relative to the execution working directory. Run them with the repository root as that working directory, or explicitly configure their data paths. Opening a notebook in its new folder does not by itself set the right input location.
- The LSTM notebooks use bare input CSV filenames relative to the execution working directory. Supply the required prepared CSV there or configure the notebook input path before running.
- EDA_Tasks/MAST90106 Group 2 EDA v2.ipynb expects its parent working directory to contain Datasets/. Its existing location has deliberately been preserved.
- nmi_agent_project and EDA_Tasks are kept at their original root-level locations because their code calculates repository paths and refers to those directory names.
- building_merge.py stays beside its building_nmi_mapping.json. Existing scripts/README.md commands still point to their original working locations.
- Existing datasets and generated results are not added by this reorganization. Some sections of the original readme describe a historical local workspace rather than tracked remote files.

No notebook or model was executed during this change.

## Preservation and duplicate checks

The source snapshot is commit 91bbc74b91a071bb64dc3754a75fd8b122ac25c2 and contains 52 tracked files.

- No two tracked files have the same Git blob SHA; no exact duplicate needed to be overwritten.
- All six loose files are moved to the locations above with their original filenames, blob SHAs and file modes.
- All 51 non-README original files retain exactly the same content. The README only receives directory-navigation and relocated-heading updates; its substantive sections are retained.
- This guide is the only new file.
- The original contents remain recoverable from the source commit.

The 20 notebooks and four JSON files were checked for valid JSON, and the 12 Python files were syntax-checked without execution. These checks do not claim that the external data or full experiment environment is available.
