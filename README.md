# FrontStory Take‑Home — Reporting

## Overview
This repo generates **daily** and optional **hourly-bonus** campaign performance reports by combining cost + revenue feeds, converting timestamps from **America/New_York** to **UTC**, aggregating per UTC day + campaign, and writing CSV outputs.

## Inputs
- **`cost_1.csv`**: cost/clicks by campaign with `data_date` in America/New_York
- **`revenue_1.csv`**: revenue by campaign with `data_date` in America/New_York

Download from the public S3 bucket (`frontstory-test-data/server-side`) into this folder. Examples (PowerShell):

```powershell
curl https://s3.amazonaws.com/frontstory-test-data/server-side/cost_1.csv -o cost_1.csv
curl https://s3.amazonaws.com/frontstory-test-data/server-side/revenue_1.csv -o revenue_1.csv
```

## Timezone conversion (America/New_York → UTC)
All `data_date` values are interpreted as **America/New_York** (EST/ET, DST-aware) and converted to **UTC** *before* bucketing. Date filtering (`--date-from`, `--date-to`) is done on **UTC day buckets** (inclusive).

## How to run
Activate your venv first:

```powershell
cd .\frontstory_takehome
.\.venv\Scripts\Activate.ps1
```

### Daily report
Writes `report.csv` by default:

```powershell
python .\report.py --date-from 2019-01-01 --date-to 2019-03-31
```

### Hourly bonus report
Adds hourly-derived columns and writes `report_hourly.csv` (example):

```powershell
python .\report.py --date-from 2019-01-01 --date-to 2019-03-31 --hourly --out report_hourly.csv
```

## Output files
- **`report.csv`**: daily metrics per campaign (UTC day) with columns, in order:
  - `date` (UTC, `YYYY/MM/DD`)
  - `campaign_id`
  - `campaign_name`
  - `total_revenue`
  - `total_cost`
  - `total_profit`
  - `total_clicks`
  - `total_roi`
  - `avg_cpc`
- **`report_hourly.csv`**: same daily metrics + hourly-derived columns:
  - `hourly_avg_revenue`
  - `positive_profit_hours`

## SQL
- `report.sql` is written against two tables (`cost_report`, `revenue_report`) mirroring the CSV schemas and returns the same daily output columns/calculations as the Python script.

## Divide-by-zero semantics
- **Python (`report.py`)**: divisions by zero (e.g. clicks = 0 or cost = 0) produce **`NaN`** in the output CSV via the `safe_div` helper.
- **SQL (`report.sql`)**: the equivalent cases produce **`NULL`** via `CASE WHEN ... THEN NULL`, which is the SQL “missing value” analogue to `NaN`.


