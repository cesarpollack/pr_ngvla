# Legacy scripts

This directory preserves scripts developed during earlier stages of the PR-ngVLA project.

## Purpose

Files in `scripts/legacy/` are retained for traceability, reproducibility, and possible reuse. Their presence here does **not** mean that they are incorrect or unusable. It means only that they are **not currently part of the active, validated analysis pipeline**.

The project is being consolidated into a final workflow. Scripts will be recovered from `legacy/` only when they are needed, reviewed against the current methodology, and either reused, revised, or replaced.

## Current workflow rule

The active `scripts/` directory should contain only scripts that are currently required and understood as part of the working pipeline.

At the present stage, the project is prioritizing the observational characterization of Puerto Rico using NOAA GHCNh hourly data for 2004–2023. Earlier analysis, diagnostic, mapping, threshold, ERA5/ERA5-Land, and other data-source scripts have therefore been archived here until they are needed again.

## Contents

The directory includes several broad groups of historical project code:

- Earlier GHCNh inventory, coverage, quality-control, cleaning, station-product, and mapping scripts.
- Earlier NOAA station-inventory and variable-coverage scripts.
- Download and processing scripts for data sources other than the current GHCNh workflow, including ERA5/ERA5-Land, PRISM, NOAA ISD, NDBC, NOAA CO-OPS, and USGS NWIS.
- Earlier Phase 1, Phase 2, and Phase 3 analysis and mapping scripts, including threshold/exceedance, composite, gap-fill, and best-region products.
- Supporting scripts created during exploratory and intermediate stages of the project.

## Important interpretation

`legacy/` is an archive, not a validated pipeline.

Before reusing a script from this directory:

1. Identify its original purpose, inputs, outputs, and dependencies.
2. Check whether its scientific assumptions still match the current project methodology.
3. Check whether referenced paths, configuration variables, thresholds, filters, or data products are still current.
4. Review any relevant project documentation and outputs produced by that script.
5. Move or recreate the script in the active project structure only after it has been reviewed and accepted for the current workflow.

Do not assume that a script is scientifically current solely because it ran successfully in an earlier stage.

## Other observational and reanalysis data sources

Scripts associated with non-GHCNh data sources are intentionally preserved here without a new audit at this stage. They document previous acquisition and analysis work and may be useful to whoever continues those parts of the project.

Their download methodology, processing assumptions, completeness, and current usability should be reviewed from the corresponding project documentation before those datasets are used again.

## GHCNh historical scripts

Several GHCNh scripts in this directory contain useful prior work on station inventories, variable coverage, quality-code diagnostics, cleaning, and observational products. These files are being preserved so that the final GHCNh workflow does not have to be rebuilt from zero.

However, the final workflow will be established from the current scientific requirements first. Relevant legacy code will then be reviewed and reused only where it supports that workflow.

## Data preservation

Moving a script into `legacy/` does not alter the raw, interim, or output datasets previously produced by the project. Existing data products remain in their corresponding project directories unless they are explicitly archived or regenerated in a later documented step.
