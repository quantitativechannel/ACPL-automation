from __future__ import annotations

import pandas as pd

from src.reports.income_reports import (
    build_cash_receipt_report,
    build_income_statement_revenue_report,
    build_income_summary_by_entity,
)


def _sample_income_postings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"entity_code": "ACPLSZ", "revenue_type": "MAA_BASE", "posting_type": "revenue_recognition", "month": "2026-01", "amount": 100.0},
            {"entity_code": "ACPLSZ", "revenue_type": "MAA_BASE", "posting_type": "revenue_recognition", "month": "2026-02", "amount": 110.0},
            {"entity_code": "ACPLHK", "revenue_type": "MAA_BASE", "posting_type": "revenue_recognition", "month": "2026-02", "amount": 50.0},
            {"entity_code": "ACPLSZ", "revenue_type": "JV_FUND_FEE", "posting_type": "revenue_recognition", "month": "2026-02", "amount": 200.0},
            {"entity_code": "XZSM", "revenue_type": "XIHE_FUND_MGMT", "posting_type": "revenue_recognition", "month": "2026-02", "amount": 300.0},
            {"entity_code": "ACPLSZ", "revenue_type": "MAA_BASE", "posting_type": "cash_receipt", "month": "2026-02", "amount": 90.0},
            {"entity_code": "ACPLHK", "revenue_type": "MAA_BASE", "posting_type": "cash_receipt", "month": "2026-02", "amount": 45.0},
            {"entity_code": "XZSM", "revenue_type": "XIHE_FUND_MGMT", "posting_type": "cash_receipt", "month": "2026-02", "amount": 250.0},
        ]
    )


def test_income_statement_report_uses_only_revenue_recognition() -> None:
    report = build_income_statement_revenue_report(_sample_income_postings(), selected_month="2026-02")

    assert set(report["revenue_type"]) == {"MAA_BASE", "JV_FUND_FEE", "XIHE_FUND_MGMT"}
    assert report["month_amount"].sum() == 660.0


def test_cash_receipt_report_uses_only_cash_receipt_postings() -> None:
    report = build_cash_receipt_report(_sample_income_postings(), selected_month="2026-02")

    assert set(report["revenue_type"]) == {"MAA_BASE", "XIHE_FUND_MGMT"}
    assert report["month_amount"].sum() == 385.0
    assert set(report["cashflow_line"]) == {"销售商品、提供劳务收到的现金"}


def test_maa_split_by_acplsz_and_acplhk_is_preserved() -> None:
    report = build_income_statement_revenue_report(_sample_income_postings(), selected_month="2026-02")
    maa = report[report["revenue_type"] == "MAA_BASE"].set_index("entity_code")

    assert maa.loc["ACPLSZ", "month_amount"] == 110.0
    assert maa.loc["ACPLHK", "month_amount"] == 50.0


def test_income_summary_includes_zhixun_with_maa_and_jv() -> None:
    summary = build_income_summary_by_entity(_sample_income_postings(), start_month="2026-01", end_month="2026-02")
    amount = summary.set_index("summary_entity").loc["旭智咨询", "amount"]

    assert amount == 410.0


def test_income_summary_includes_xuzhi_private_with_xihe_fund() -> None:
    summary = build_income_summary_by_entity(_sample_income_postings(), start_month="2026-01", end_month="2026-02")
    amount = summary.set_index("summary_entity").loc["旭智私募", "amount"]

    assert amount == 300.0


def test_ytd_calculation_for_income_statement_and_cash_receipt() -> None:
    postings = _sample_income_postings()

    income_report = build_income_statement_revenue_report(postings, selected_month="2026-02", entity_code="ACPLSZ")
    maa_income = income_report[income_report["revenue_type"] == "MAA_BASE"].iloc[0]

    cash_report = build_cash_receipt_report(postings, selected_month="2026-02", entity_code="ACPLSZ")
    maa_cash = cash_report[cash_report["revenue_type"] == "MAA_BASE"].iloc[0]

    assert maa_income["month_amount"] == 110.0
    assert maa_income["ytd_amount"] == 210.0
    assert maa_cash["month_amount"] == 90.0
    assert maa_cash["ytd_amount"] == 90.0
