from __future__ import annotations

import pandas as pd


def company_summary(expenses: pd.DataFrame, scenarios: list[str]) -> pd.DataFrame:
    scoped = expenses[expenses["scenario"].isin(scenarios)].copy()
    grouped = (
        scoped.groupby(["company", "scenario", "month"], as_index=False)
        .agg(expense=("expense", "sum"))
        .sort_values(["company", "scenario", "month"])
    )
    return grouped


def consolidated_summary(expenses: pd.DataFrame, scenarios: list[str]) -> pd.DataFrame:
    scoped = expenses[expenses["scenario"].isin(scenarios)].copy()
    grouped = scoped.groupby(["scenario", "month"], as_index=False).agg(expense=("expense", "sum")).sort_values(
        ["scenario", "month"]
    )
    grouped["net_flow"] = -grouped["expense"]
    return grouped


def cash_flow(expenses: pd.DataFrame, scenarios: list[str], opening_cash: float = 0.0) -> pd.DataFrame:
    consolidated = consolidated_summary(expenses, scenarios)
    frames: list[pd.DataFrame] = []

    for scenario, frame in consolidated.groupby("scenario"):
        ordered = frame.sort_values("month").copy()
        ordered["scenario"] = scenario
        ordered["closing_cash"] = opening_cash + ordered["net_flow"].cumsum()
        frames.append(ordered)

    if not frames:
        return consolidated.assign(closing_cash=pd.Series(dtype=float))

    return pd.concat(frames, ignore_index=True)


def scenario_reports(expenses: pd.DataFrame, scenarios: list[str], opening_cash: float = 0.0) -> dict[str, pd.DataFrame]:
    cash = cash_flow(expenses, scenarios, opening_cash)
    reports: dict[str, pd.DataFrame] = {}
    for scenario in scenarios:
        scenario_cash = cash[cash["scenario"] == scenario]
        reports[scenario] = scenario_cash[["month", "expense", "net_flow", "closing_cash"]].copy()
    return reports
