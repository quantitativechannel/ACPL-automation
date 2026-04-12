# ACPL Budget Forecasting Automation

This repository contains a starter app for automating budget forecasting from an existing Excel workbook.

## What it does

- Reads an `Expenses` tab from your Excel file.
- Lets you edit company-level forecasts in a simple Streamlit app.
- Builds:
  - Company-level budget vs expense summary
  - Consolidated summary across all companies
  - Cash flow projection by scenario
  - Scenario-specific report tabs
- Exports a refreshed Excel workbook for sharing.

## Expected `Expenses` columns

The app expects these columns in the `Expenses` sheet:

- `company`
- `person`
- `item`
- `scenario`
- `month`
- `budget`
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
