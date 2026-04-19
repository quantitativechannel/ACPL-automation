# ACPL Budget Forecasting Automation

This repository contains a Streamlit app and budgeting engine for ACPL budgeting automation with subsidiary-level inputs and consolidated reporting.

## What it does

- Uploads and maintains legacy `Expenses` workbooks.
- Supports subsidiary-specific annual expense assumptions via manual grid edits and spreadsheet upload.
- Auto-allocates annual costs into monthly values using configurable methods:
  - `monthly_average`
  - `quarterly`
  - `particular_month`
- Supports expense assumption uploads (`code`, `expense_item`, `cashflow_item`) and auto-populates them across subsidiaries.
- Adds a `People` tab to upload people assumptions with columns `person`, `location`, and `base_salary`.
- Builds:
  - company-level expense summary
  - consolidated summary across companies
  - cash flow projection by scenario
  - scenario-specific report tabs
- Exports a refreshed Excel workbook for sharing.

## Expected columns

### Expense assumptions upload

- `code`
- `expense_item`
- `cashflow_item`
- `scenario`
- `annual_cost`
- `allocation_method`
- optional: `year`, `allocation_month`

### Subsidiary projection upload

- `code`
- `expense_item`
- `cashflow_item`
- optional: `scenario`, `year`, `annual_cost`, `allocation_method`, `allocation_month`

### People upload

- `person`
- `location`
- `base_salary`

### Legacy `Expenses` sheet

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
streamlit run acpl.py
```

## Tests

```bash
pytest
```
