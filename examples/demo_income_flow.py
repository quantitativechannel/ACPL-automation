from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.drivers.income_capacity_driver import build_capacity_rollforward
from src.drivers.maa_revenue_driver import build_maa_postings


def _build_demo_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    months = pd.period_range("2026-01", "2026-12", freq="M").astype(str).tolist()
    capacity_assumptions = pd.DataFrame([
        {"scenario_id": "DEMO", "project_group": "Solar", "month": month, "new_capacity_w": 100_000, "addition_timing_factor": 0.5, "avg_equity_price_per_w": 0.2}
        for month in months
    ])
    maa_assumptions = pd.DataFrame([
        {"scenario_id": "DEMO", "project_group": "Solar", "month": month, "incentive_1_flag": 1, "incentive_2_flag": 0, "reimbursed_cost_ex_vat": 1000.0 if month.endswith("-12") else 0.0}
        for month in months
    ])
    revenue_policies = pd.DataFrame([
        {"revenue_type": "MAA_BASE", "rate": 0.10, "vat_rate": 0.06, "cit_rate": 0.25},
        {"revenue_type": "MAA_INCENTIVE_1", "rate": 0.01, "vat_rate": 0.06, "cit_rate": 0.25},
        {"revenue_type": "MAA_INCENTIVE_2", "rate": 0.04, "vat_rate": 0.06, "cit_rate": 0.25},
    ])
    allocation_rules = pd.DataFrame([
        {"revenue_type": "MAA_BASE", "recipient_entity_code": "ACPLSZ", "allocation_pct": 0.70, "haircut_pct": 0.00},
        {"revenue_type": "MAA_BASE", "recipient_entity_code": "ACPLHK", "allocation_pct": 0.30, "haircut_pct": 0.05},
        {"revenue_type": "MAA_INCENTIVE_1", "recipient_entity_code": "ACPLSZ", "allocation_pct": 0.70, "haircut_pct": 0.00},
        {"revenue_type": "MAA_INCENTIVE_1", "recipient_entity_code": "ACPLHK", "allocation_pct": 0.30, "haircut_pct": 0.05},
        {"revenue_type": "MAA_INCENTIVE_2", "recipient_entity_code": "ACPLSZ", "allocation_pct": 0.70, "haircut_pct": 0.00},
        {"revenue_type": "MAA_INCENTIVE_2", "recipient_entity_code": "ACPLHK", "allocation_pct": 0.30, "haircut_pct": 0.05},
    ])
    cash_collection_rules = pd.DataFrame([
        {"revenue_type": "MAA_BASE", "collection_method": "quarterly_prepaid", "collection_months": "1,4,7,10", "settlement_month": None},
        {"revenue_type": "MAA_INCENTIVE_1", "collection_method": "annual_settlement", "collection_months": None, "settlement_month": None},
        {"revenue_type": "MAA_INCENTIVE_2", "collection_method": "full_cycle_settlement", "collection_months": None, "settlement_month": "2030-12"},
    ])
    fund_assumptions = pd.DataFrame([
        {"scenario_id": "DEMO", "fund_name": "JV Fund", "month": "2026-01", "fixed_expense_contribution": 600000.0},
        {"scenario_id": "DEMO", "fund_name": "XiHe Fund", "month": "2026-01", "fixed_expense_contribution": 240000.0},
    ])
    return capacity_assumptions, maa_assumptions, revenue_policies, allocation_rules, cash_collection_rules, fund_assumptions


def _build_fund_postings(scenario_id: str, fund_assumptions_df: pd.DataFrame) -> pd.DataFrame:
    jan = fund_assumptions_df[fund_assumptions_df["month"] == "2026-01"].set_index("fund_name")["fixed_expense_contribution"]
    return pd.DataFrame([
        {"scenario_id": scenario_id, "entity_code": "旭智咨询", "month": "2026-01", "account_code": "FUND_REVENUE", "posting_type": "revenue_recognition", "revenue_type": "JV_FUND", "source_module": "fund_demo", "reference_id": "JV_FUND|DEMO|2026-01", "description": "JV fund management fee", "amount": float(jan.get("JV Fund", 0.0))},
        {"scenario_id": scenario_id, "entity_code": "旭智私募", "month": "2026-01", "account_code": "FUND_REVENUE", "posting_type": "revenue_recognition", "revenue_type": "XIHE_FUND", "source_module": "fund_demo", "reference_id": "XIHE_FUND|DEMO|2026-01", "description": "XiHe fund management fee", "amount": float(jan.get("XiHe Fund", 0.0))},
        {"scenario_id": scenario_id, "entity_code": "旭智私募", "month": "2026-01", "account_code": "CASH_RECEIPT_SERVICES", "posting_type": "cash_receipt", "revenue_type": "ANNUAL_PREPAID", "source_module": "fund_demo", "reference_id": "ANNUAL_PREPAID|DEMO|2026-01", "description": "Annual prepaid cash receipt", "amount": 120000.0},
    ])


def _build_income_statement_report(postings: pd.DataFrame) -> pd.DataFrame:
    revenue = postings[postings["posting_type"] == "revenue_recognition"].copy()
    revenue["year"] = revenue["month"].str[:4]
    revenue = revenue.sort_values(["entity_code", "month"])
    revenue["ytd_revenue"] = revenue.groupby(["scenario_id", "entity_code", "year"])["amount"].cumsum()
    return revenue[["scenario_id", "entity_code", "month", "revenue_type", "amount", "ytd_revenue"]]


def _build_cash_receipt_report(postings: pd.DataFrame) -> pd.DataFrame:
    cash = postings[postings["posting_type"] == "cash_receipt"].copy()
    return cash.sort_values(["month", "entity_code"])


def main() -> None:
    output_dir = Path("examples/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    capacity_assumptions, maa_assumptions, revenue_policies, allocation_rules, cash_collection_rules, fund_assumptions = _build_demo_inputs()
    capacity_rollforward = build_capacity_rollforward(capacity_assumptions, "2026-01", "2026-12")
    maa_postings = build_maa_postings(capacity_rollforward, maa_assumptions, revenue_policies, allocation_rules, cash_collection_rules, "2026-01", "2026-12")
    fund_postings = _build_fund_postings("DEMO", fund_assumptions)
    all_postings = pd.concat([maa_postings, fund_postings], ignore_index=True)
    income_statement = _build_income_statement_report(all_postings)
    cash_receipts = _build_cash_receipt_report(all_postings)
    outputs = {
        "capacity_assumptions.csv": capacity_assumptions,
        "maa_assumptions.csv": maa_assumptions,
        "revenue_policies.csv": revenue_policies,
        "allocation_rules.csv": allocation_rules,
        "cash_collection_rules.csv": cash_collection_rules,
        "fund_assumptions.csv": fund_assumptions,
        "capacity_rollforward.csv": capacity_rollforward,
        "maa_postings.csv": maa_postings,
        "fund_postings.csv": fund_postings,
        "all_postings.csv": all_postings,
        "income_statement_revenue.csv": income_statement,
        "cash_receipts.csv": cash_receipts,
    }
    for fn, df in outputs.items():
        p = output_dir / fn
        df.to_csv(p, index=False)
        print(f"saved {p}")


if __name__ == "__main__":
    main()
