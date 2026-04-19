from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd

REQUIRED_COLUMNS = {
    "company",
    "code",
    "expense_item",
    "cashflow_item",
    "scenario",
    "month",
    "annual_cost",
    "allocation_method",
    "allocation_month",
    "expense",
}

ALLOCATION_METHODS = {
    "monthly_average",
    "quarterly",
    "quarterly_start",
    "quarterly_end",
    "specific_month",
    "particular_month",
}
EXPENSE_UPLOAD_REQUIRED = {"code", "expense_item", "cashflow_item"}
TRIP_CATEGORIES = ["Shenzhen/HK", "Short Dist", "Long Dist", "International"]
TRAVEL_EXPENSE_ITEMS = [
    "Airfare -International",
    "Airfare-Domestic",
    "Ground Transportation",
    "Hotels",
    "Meals",
]


def sync_trip_type_config(people_df: pd.DataFrame, trip_config_df: pd.DataFrame | None = None) -> pd.DataFrame:
    people = people_df.copy()
    people.columns = [str(c).strip().lower() for c in people.columns]
    if "type" not in people.columns:
        return pd.DataFrame(columns=["type", "category", "est_trips", "cost_per_trip"])

    ordered_types: list[str] = []
    seen_types: set[str] = set()
    for raw_type in people["type"].fillna("").astype(str):
        type_value = raw_type.strip()
        if type_value and type_value not in seen_types:
            seen_types.add(type_value)
            ordered_types.append(type_value)

    if not ordered_types:
        return pd.DataFrame(columns=["type", "category", "est_trips", "cost_per_trip"])

    existing = trip_config_df.copy() if trip_config_df is not None else pd.DataFrame()
    existing.columns = [str(c).strip().lower() for c in existing.columns]
    for column in ["type", "category", "est_trips", "cost_per_trip"]:
        if column not in existing.columns:
            existing[column] = pd.Series(dtype="object" if column in {"type", "category"} else "float64")

    existing = existing[["type", "category", "est_trips", "cost_per_trip"]].copy()
    existing["type"] = existing["type"].fillna("").astype(str).str.strip()
    existing["category"] = existing["category"].fillna("").astype(str).str.strip()
    existing["est_trips"] = pd.to_numeric(existing["est_trips"], errors="coerce").fillna(0.0)
    existing["cost_per_trip"] = pd.to_numeric(existing["cost_per_trip"], errors="coerce").fillna(0.0)
    existing = existing[(existing["type"] != "") & (existing["category"] != "")]
    existing = existing.drop_duplicates(subset=["type", "category"], keep="first")

    template = pd.DataFrame(
        [{"type": type_value, "category": category} for type_value in ordered_types for category in TRIP_CATEGORIES]
    )
    synced = template.merge(existing, on=["type", "category"], how="left")
    synced["est_trips"] = synced["est_trips"].fillna(0.0)
    synced["cost_per_trip"] = synced["cost_per_trip"].fillna(0.0)
    return synced[["type", "category", "est_trips", "cost_per_trip"]]


@dataclass
class BudgetWorkbook:
    expenses: pd.DataFrame

    @classmethod
    def from_excel(cls, file: BinaryIO | BytesIO) -> "BudgetWorkbook":
        raw = pd.read_excel(file, sheet_name="Expenses")
        normalized = _normalize_expenses(raw)
        return cls(expenses=normalized)

    def apply_company_updates(self, company: str, edited_company_df: pd.DataFrame) -> None:
        remainder = self.expenses[self.expenses["company"] != company].copy()
        updated_company = _normalize_expenses(edited_company_df)
        self.expenses = pd.concat([remainder, updated_company], ignore_index=True)

    def upload_expense_assumptions(self, assumptions_df: pd.DataFrame) -> None:
        companies = sorted(self.expenses["company"].dropna().astype(str).str.strip().unique().tolist())
        if not companies:
            raise ValueError("No subsidiaries/companies found in current workbook.")

        uploaded = allocate_expenses_to_companies(assumptions_df=assumptions_df, companies=companies)
        self.expenses = pd.concat([self.expenses, uploaded], ignore_index=True).sort_values(
            ["company", "scenario", "month", "code", "expense_item"]
        )

    def company_summary(self, scenarios: list[str]) -> pd.DataFrame:
        scoped = self.expenses[self.expenses["scenario"].isin(scenarios)].copy()
        grouped = (
            scoped.groupby(["company", "scenario", "month"], as_index=False)
            .agg(expense=("expense", "sum"))
            .sort_values(["company", "scenario", "month"])
        )
        return grouped

    def consolidated_summary(self, scenarios: list[str]) -> pd.DataFrame:
        scoped = self.expenses[self.expenses["scenario"].isin(scenarios)].copy()
        grouped = (
            scoped.groupby(["scenario", "month"], as_index=False)
            .agg(expense=("expense", "sum"))
            .sort_values(["scenario", "month"])
        )
        grouped["net_flow"] = -grouped["expense"]
        return grouped

    def cash_flow(self, scenarios: list[str], opening_cash: float = 0.0) -> pd.DataFrame:
        consolidated = self.consolidated_summary(scenarios)
        frames: list[pd.DataFrame] = []

        for scenario, frame in consolidated.groupby("scenario"):
            ordered = frame.sort_values("month").copy()
            ordered["scenario"] = scenario
            ordered["closing_cash"] = opening_cash + ordered["net_flow"].cumsum()
            frames.append(ordered)

        if not frames:
            return consolidated.assign(closing_cash=pd.Series(dtype=float))

        return pd.concat(frames, ignore_index=True)

    def scenario_reports(self, scenarios: list[str], opening_cash: float = 0.0) -> dict[str, pd.DataFrame]:
        cash = self.cash_flow(scenarios, opening_cash)
        reports: dict[str, pd.DataFrame] = {}
        for scenario in scenarios:
            scenario_cash = cash[cash["scenario"] == scenario]
            reports[scenario] = scenario_cash[["month", "expense", "net_flow", "closing_cash"]].copy()
        return reports


def generate_forecast_table(
    assumptions_df: pd.DataFrame,
    company: str,
    end_year: int,
    annual_growth_pct: float,
    start_year: int | None = None,
) -> pd.DataFrame:
    start_year = start_year or pd.Timestamp.today().year
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    base = assumptions_df.copy()
    base.columns = [str(c).strip().lower() for c in base.columns]

    missing = EXPENSE_UPLOAD_REQUIRED.difference(base.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Forecast source is missing required columns: {missing_str}")

    if "annual_cost" not in base.columns:
        base["annual_cost"] = 0.0
    if "allocation_method" not in base.columns:
        base["allocation_method"] = "monthly_average"
    if "allocation_month" not in base.columns:
        base["allocation_month"] = 1

    base["annual_cost"] = pd.to_numeric(base["annual_cost"], errors="coerce").fillna(0.0)
    growth_factor = 1 + (annual_growth_pct / 100.0)

    long_rows: list[dict] = []
    for year in range(start_year, end_year + 1):
        year_multiplier = growth_factor ** (year - start_year)
        yearly = base.copy()
        yearly["company"] = company
        yearly["scenario"] = "Forecast"
        yearly["year"] = year
        yearly["annual_cost"] = yearly["annual_cost"] * year_multiplier
        allocated = _expand_annual_rows(yearly)
        long_rows.extend(allocated.to_dict("records"))

    long_df = pd.DataFrame(long_rows)
    if long_df.empty:
        return pd.DataFrame()

    long_df["month_label"] = pd.to_datetime(long_df["month"]).dt.strftime("%Y-%m")
    detail_cols = ["company", "code", "expense_item", "cashflow_item", "allocation_method", "allocation_month"]
    wide = (
        long_df.pivot_table(index=detail_cols, columns="month_label", values="expense", aggfunc="sum", fill_value=0.0)
        .reset_index()
        .sort_values(["code", "expense_item"])
    )
    annual_lookup = (
        base[["code", "expense_item", "annual_cost"]]
        .drop_duplicates(subset=["code", "expense_item"], keep="last")
        .rename(columns={"annual_cost": "annual_cost_assumption"})
    )
    wide = wide.merge(annual_lookup, on=["code", "expense_item"], how="left")
    ordered = [
        "company",
        "code",
        "expense_item",
        "cashflow_item",
        "annual_cost_assumption",
        "allocation_method",
        "allocation_month",
    ]
    month_cols = [c for c in wide.columns if c not in ordered]
    wide = wide[ordered + month_cols]
    wide.columns.name = None
    return wide


def build_travel_assumptions_from_people(
    people_df: pd.DataFrame,
    trip_config_df: pd.DataFrame,
    allocation_df: pd.DataFrame,
    master_config_df: pd.DataFrame | None = None,
    scenario: str = "Base",
    year: int | None = None,
) -> pd.DataFrame:
    if year is None:
        year = pd.Timestamp.today().year

    people = people_df.copy()
    people.columns = [str(c).strip().lower() for c in people.columns]
    people = people.rename(columns={"person": "name"})
    required_people = {"name", "location", "company", "base_salary", "type"}
    missing_people = required_people.difference(people.columns)
    if missing_people:
        raise ValueError(f"People table missing required columns: {', '.join(sorted(missing_people))}")

    people["company"] = people["company"].astype(str).str.strip()
    people["type"] = people["type"].astype(str).str.strip()
    people = people[(people["company"] != "") & (people["type"] != "")]
    if people.empty:
        return pd.DataFrame()

    trip_cfg = trip_config_df.copy()
    trip_cfg.columns = [str(c).strip().lower() for c in trip_cfg.columns]
    required_trip = {"type", "category", "est_trips", "cost_per_trip"}
    missing_trip = required_trip.difference(trip_cfg.columns)
    if missing_trip:
        raise ValueError(f"Trip configuration missing columns: {', '.join(sorted(missing_trip))}")
    trip_cfg = trip_cfg[list(required_trip)].copy()
    trip_cfg["type"] = trip_cfg["type"].astype(str).str.strip()
    trip_cfg["category"] = trip_cfg["category"].astype(str).str.strip()
    trip_cfg["est_trips"] = pd.to_numeric(trip_cfg["est_trips"], errors="coerce").fillna(0.0)
    trip_cfg["cost_per_trip"] = pd.to_numeric(trip_cfg["cost_per_trip"], errors="coerce").fillna(0.0)
    trip_cfg = trip_cfg[(trip_cfg["type"] != "") & (trip_cfg["category"] != "")]

    alloc_cfg = allocation_df.copy()
    alloc_cfg.columns = [str(c).strip().lower() for c in alloc_cfg.columns]
    required_alloc = {"category", "expense_item", "allocation_pct"}
    missing_alloc = required_alloc.difference(alloc_cfg.columns)
    if missing_alloc:
        raise ValueError(f"Allocation configuration missing columns: {', '.join(sorted(missing_alloc))}")
    alloc_cfg = alloc_cfg[list(required_alloc)].copy()
    alloc_cfg["category"] = alloc_cfg["category"].astype(str).str.strip()
    alloc_cfg["expense_item"] = alloc_cfg["expense_item"].astype(str).str.strip()
    alloc_cfg["allocation_pct"] = pd.to_numeric(alloc_cfg["allocation_pct"], errors="coerce").fillna(0.0)
    alloc_cfg = alloc_cfg[(alloc_cfg["category"] != "") & (alloc_cfg["expense_item"] != "")]

    if trip_cfg.empty or alloc_cfg.empty:
        return pd.DataFrame()

    headcount = people.groupby(["company", "type"], as_index=False).agg(headcount=("name", "count"))
    cost_by_category = headcount.merge(trip_cfg, on="type", how="inner")
    if cost_by_category.empty:
        return pd.DataFrame()

    cost_by_category["annual_category_cost"] = (
        cost_by_category["headcount"] * cost_by_category["est_trips"] * cost_by_category["cost_per_trip"]
    )
    company_item_cost = cost_by_category.merge(alloc_cfg, on="category", how="inner")
    if company_item_cost.empty:
        return pd.DataFrame()

    company_item_cost["annual_cost"] = company_item_cost["annual_category_cost"] * (
        company_item_cost["allocation_pct"] / 100.0
    )
    annualized = (
        company_item_cost.groupby(["company", "expense_item"], as_index=False)
        .agg(annual_cost=("annual_cost", "sum"))
        .sort_values(["company", "expense_item"])
    )

    config_lookup = pd.DataFrame(columns=["expense_item", "code", "cashflow_item"])
    if master_config_df is not None and not master_config_df.empty:
        cfg = master_config_df.copy()
        cfg.columns = [str(c).strip().lower() for c in cfg.columns]
        cfg["expense_item"] = cfg["expense_item"].astype(str).str.strip()
        config_lookup = (
            cfg[["expense_item", "code", "cashflow_item"]].drop_duplicates(subset=["expense_item"], keep="first").copy()
        )

    annualized = annualized.merge(config_lookup, on="expense_item", how="left")
    generated_code = annualized["expense_item"].str.upper().str.replace(r"[^A-Z0-9]+", "_", regex=True).str.strip("_")
    annualized["code"] = annualized["code"].fillna("TRAVEL_" + generated_code)
    annualized["cashflow_item"] = annualized["cashflow_item"].fillna("Operating Expense")
    annualized["scenario"] = scenario
    annualized["year"] = int(year)
    annualized["allocation_method"] = "monthly_average"
    annualized["allocation_month"] = 1

    return annualized[
        [
            "company",
            "code",
            "expense_item",
            "cashflow_item",
            "scenario",
            "year",
            "annual_cost",
            "allocation_method",
            "allocation_month",
        ]
    ]


def _normalize_expenses(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    if "item" in df.columns and "expense_item" not in df.columns:
        df["expense_item"] = df["item"]
    if "person" in df.columns and "code" not in df.columns:
        df["code"] = df["person"]
    if "cashflow_item" not in df.columns:
        df["cashflow_item"] = "Operating Expense"
    if "annual_cost" not in df.columns and "expense" in df.columns:
        df["annual_cost"] = pd.to_numeric(df["expense"], errors="coerce").fillna(0.0)
    if "allocation_method" not in df.columns:
        df["allocation_method"] = "specific_month"
    if "allocation_month" not in df.columns:
        month_source = pd.to_datetime(df.get("month"), errors="coerce")
        df["allocation_month"] = month_source.dt.month.fillna(1).astype(int)

    if "year" not in df.columns:
        month_source = pd.to_datetime(df.get("month"), errors="coerce")
        df["year"] = month_source.dt.year.fillna(pd.Timestamp.today().year).astype(int)

    if "expense" not in df.columns:
        expanded = _expand_annual_rows(df)
    else:
        expanded = df.copy()

    missing = REQUIRED_COLUMNS.difference(expanded.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Expenses sheet is missing required columns: {missing_str}")

    expanded = expanded[list(REQUIRED_COLUMNS)].copy()
    expanded["month"] = pd.to_datetime(expanded["month"]).dt.to_period("M").dt.to_timestamp()
    expanded["annual_cost"] = pd.to_numeric(expanded["annual_cost"], errors="coerce").fillna(0.0)
    expanded["allocation_month"] = pd.to_numeric(expanded["allocation_month"], errors="coerce").fillna(1).astype(int)
    expanded["expense"] = pd.to_numeric(expanded["expense"], errors="coerce").fillna(0.0)

    for text_col in ["company", "code", "expense_item", "cashflow_item", "scenario", "allocation_method"]:
        expanded[text_col] = expanded[text_col].astype(str).str.strip()

    return expanded.sort_values(["company", "scenario", "month", "code", "expense_item"]).reset_index(drop=True)


def allocate_expenses_to_companies(assumptions_df: pd.DataFrame, companies: list[str]) -> pd.DataFrame:
    assumptions = assumptions_df.copy()
    assumptions.columns = [str(c).strip().lower() for c in assumptions.columns]
    missing = EXPENSE_UPLOAD_REQUIRED.difference(assumptions.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Expense upload is missing required columns: {missing_str}")

    assumptions["code"] = assumptions["code"].astype(str).str.strip()
    assumptions["expense_item"] = assumptions["expense_item"].astype(str).str.strip()
    assumptions["cashflow_item"] = assumptions["cashflow_item"].astype(str).str.strip()
    assumptions = assumptions[(assumptions["code"] != "") & (assumptions["expense_item"] != "")]
    if assumptions.empty:
        raise ValueError("Expense upload does not contain any valid rows.")

    if "scenario" not in assumptions.columns:
        assumptions["scenario"] = "Base"
    if "annual_cost" not in assumptions.columns:
        assumptions["annual_cost"] = 0.0
    if "allocation_method" not in assumptions.columns:
        assumptions["allocation_method"] = "monthly_average"
    if "year" not in assumptions.columns:
        assumptions["year"] = pd.Timestamp.today().year
    if "allocation_month" not in assumptions.columns:
        assumptions["allocation_month"] = 1

    expanded_rows: list[dict] = []
    for company in companies:
        company_rows = assumptions.copy()
        company_rows["company"] = company
        expanded_rows.extend(_expand_annual_rows(company_rows).to_dict("records"))

    return _normalize_expenses(pd.DataFrame(expanded_rows))


def _expand_annual_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, row in df.iterrows():
        method = str(row["allocation_method"]).strip().lower()
        if method not in ALLOCATION_METHODS:
            raise ValueError(
                f"Unsupported allocation_method '{method}'. Use one of: {', '.join(sorted(ALLOCATION_METHODS))}."
            )

        annual = float(pd.to_numeric(row["annual_cost"], errors="coerce") or 0.0)
        year = int(pd.to_numeric(row.get("year", pd.Timestamp.today().year), errors="coerce") or pd.Timestamp.today().year)
        alloc_month_val = pd.to_numeric(row.get("allocation_month", 1), errors="coerce")
        if pd.isna(alloc_month_val):
            alloc_month_val = 1
        alloc_month = int(alloc_month_val)
        alloc_month = min(max(1, alloc_month), 12)

        months = pd.date_range(f"{year}-01-01", periods=12, freq="MS")
        expense_by_month = {m: 0.0 for m in months}

        if method == "monthly_average":
            monthly_value = annual / 12.0
            for m in months:
                expense_by_month[m] = monthly_value
        elif method in {"quarterly", "quarterly_start"}:
            quarter_months = [1, 4, 7, 10]
            quarterly_value = annual / 4.0
            for m in months:
                if m.month in quarter_months:
                    expense_by_month[m] = quarterly_value
        elif method == "quarterly_end":
            quarter_months = [3, 6, 9, 12]
            quarterly_value = annual / 4.0
            for m in months:
                if m.month in quarter_months:
                    expense_by_month[m] = quarterly_value
        else:
            for m in months:
                if m.month == alloc_month:
                    expense_by_month[m] = annual

        for m in months:
            rows.append(
                {
                    "company": row["company"],
                    "code": row["code"],
                    "expense_item": row["expense_item"],
                    "cashflow_item": row["cashflow_item"],
                    "scenario": row["scenario"],
                    "month": m,
                    "annual_cost": annual,
                    "allocation_method": method,
                    "allocation_month": alloc_month,
                    "expense": expense_by_month[m],
                }
            )

    return pd.DataFrame(rows)


def export_dashboard_workbook(
    file_obj: BinaryIO | BytesIO,
    expenses_df: pd.DataFrame,
    opening_cash: float,
    scenarios: list[str],
) -> None:
    workbook = BudgetWorkbook(expenses=expenses_df)
    company_summary = workbook.company_summary(scenarios)
    consolidated = workbook.consolidated_summary(scenarios)
    cash_flow = workbook.cash_flow(scenarios, opening_cash)
    reports = workbook.scenario_reports(scenarios, opening_cash)

    with pd.ExcelWriter(file_obj, engine="xlsxwriter") as writer:
        workbook.expenses.to_excel(writer, sheet_name="Expenses", index=False)
        company_summary.to_excel(writer, sheet_name="Company Summary", index=False)
        consolidated.to_excel(writer, sheet_name="Consolidated", index=False)
        cash_flow.to_excel(writer, sheet_name="Cash Flow", index=False)

        for scenario, frame in reports.items():
            safe_name = str(scenario)[:27]
            frame.to_excel(writer, sheet_name=f"Report {safe_name}", index=False)


def default_template() -> bytes:
    template = pd.DataFrame(
        [
            {
                "company": "Company A",
                "code": "MKT-001",
                "expense_item": "Marketing",
                "cashflow_item": "Operating Expense",
                "scenario": "Base",
                "year": 2026,
                "annual_cost": 24000,
                "allocation_method": "monthly_average",
                "allocation_month": 1,
            },
            {
                "company": "Company B",
                "code": "OPS-100",
                "expense_item": "Compliance Filing",
                "cashflow_item": "Operating Expense",
                "scenario": "Conservative",
                "year": 2026,
                "annual_cost": 12000,
                "allocation_method": "quarterly_end",
                "allocation_month": 1,
            },
        ]
    )
    normalized = _normalize_expenses(template)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        normalized.to_excel(writer, sheet_name="Expenses", index=False)

    buffer.seek(0)
    return buffer.getvalue()
