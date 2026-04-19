# ACPL Budget Forecasting Automation

This repository contains a Streamlit app and budgeting engine for ACPL budgeting automation with subsidiary-level inputs and consolidated reporting.

## What it does

- Uploads and maintains legacy `Expenses` workbooks.
- Supports subsidiary-specific monthly input via manual grid edits and spreadsheet upload.
- Generates annual projections where:
  - monthly values stay flat within a year
  - growth is applied only when moving to the next year
- Supports expense assumption uploads (`code`, `expense_item`, `cashflow_item`) and auto-populates them across subsidiaries.
- Allocates annual costs by method:
  - `monthly_average`
  - `quarterly`
  - `particular_month`
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

- `item`
- `monthly_budget`
- `monthly_expense`

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
