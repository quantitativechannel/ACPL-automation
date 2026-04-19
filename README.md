# ACPL Budget Forecasting Automation

This repository contains a Streamlit app for ACPL budgeting automation with subsidiary-level inputs and consolidated reporting.

## What it does

<<<<<<< ours
- Uploads and maintains an expense mapping (`expense_item -> cashflow_item`).
- Uploads personnel data (`person`, `location`, `salary`).
- Supports subsidiary-specific monthly input via manual grid edits and spreadsheet upload.
- Generates annual projections where:
  - monthly values are flat within a year
  - growth is applied only when moving to the next year
- Consolidates subsidiary projections into a master tab.
- Preserves a legacy workflow for existing `Expenses` workbooks and export.
=======
- Reads an `Expenses` tab from your Excel file.
- Lets you edit annual expense assumptions in a Streamlit app.
- Supports expense assumption uploads (`code`, `expense_item`, `cashflow_item`) and auto-populates them across all subsidiaries.
- Allocates annual costs by method:
  - `monthly_average`
  - `quarterly`
  - `particular_month`
- Builds:
  - Company-level expense summary
  - Consolidated summary across all companies
  - Cash flow projection by scenario
  - Scenario-specific report tabs
- Exports a refreshed Excel workbook for sharing.
>>>>>>> theirs

## Expected columns

### Mapping upload

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
- `expense_item`
- `cashflow_item`

### Personnel upload

<<<<<<< ours
- `person`
- `location`
- `salary`

### Subsidiary expense upload

- `item`
- `monthly_budget`
- `monthly_expense`

### Legacy `Expenses` sheet

The legacy flow expects:

=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
- `company`
- `code`
- `expense_item`
- `cashflow_item`
- `scenario`
- `month`
- `annual_cost`
- `allocation_method`
- `allocation_month`
- `expense`

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run acpl_app.py
```

## Tests

```bash
pytest
```
