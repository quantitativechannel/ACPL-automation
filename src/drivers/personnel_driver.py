import pandas as pd

PERSONNEL_OUTPUT_COLUMNS = [
    "scenario_id",
    "entity_id",
    "month",
    "account_code",
    "posting_type",
    "source_module",
    "reference_id",
    "description",
    "amount",
    "employee_id",
    "employee_name",
    "cost_component",
]

HEADCOUNT_OUTPUT_COLUMNS = ["scenario_id", "entity_id", "month", "role_type", "active_headcount"]


def _month_period(value: object) -> pd.Period:
    return pd.Period(str(value), freq="M")


def _active_employee_months(employees_df: pd.DataFrame, start_month: str, end_month: str) -> pd.DataFrame:
    if employees_df.empty:
        return pd.DataFrame(columns=list(employees_df.columns) + ["month"])

    start_period = pd.Period(start_month, freq="M")
    end_period = pd.Period(end_month, freq="M")
    month_index = pd.period_range(start=start_period, end=end_period, freq="M")

    employees = employees_df.copy()
    employees["active_flag"] = pd.to_numeric(employees["active_flag"], errors="coerce").fillna(0)
    employees = employees[employees["active_flag"] == 1].copy()
    if employees.empty:
        return pd.DataFrame(columns=list(employees_df.columns) + ["month"])

    employees["start_period"] = pd.to_datetime(employees["start_date"], errors="coerce").dt.to_period("M").fillna(start_period)
    employees["end_period"] = pd.to_datetime(employees["end_date"], errors="coerce").dt.to_period("M").fillna(end_period)

    employees["month_list"] = employees.apply(
        lambda r: [m for m in month_index if m >= r["start_period"] and m <= r["end_period"]],
        axis=1,
    )
    employees = employees.explode("month_list").rename(columns={"month_list": "month"})
    employees = employees[employees["month"].notna()].copy()
    employees["month"] = employees["month"].astype("period[M]")
    return employees


def build_personnel_postings(
    employees_df: pd.DataFrame,
    burden_rules_df: pd.DataFrame,
    start_month: str,
    end_month: str,
    bonus_rules_df: pd.DataFrame | None = None,
    medical_rules_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    active = _active_employee_months(employees_df, start_month, end_month)
    if active.empty:
        return pd.DataFrame(columns=PERSONNEL_OUTPUT_COLUMNS)

    burden = burden_rules_df.copy()
    merged = active.merge(burden, on="location", how="left")
    merged["base_salary"] = pd.to_numeric(merged["base_salary"], errors="coerce").fillna(0.0)

    records: list[dict] = []

    def add_records(df: pd.DataFrame, account_col: str, amount_series: pd.Series, component: str) -> None:
        valid = df[account_col].notna() & (amount_series != 0)
        for _, row in df[valid].iterrows():
            records.append(
                {
                    "scenario_id": row["scenario_id"],
                    "entity_id": row["entity_id"],
                    "month": row["month"].strftime("%Y-%m"),
                    "account_code": row[account_col],
                    "posting_type": "expense",
                    "source_module": "personnel",
                    "reference_id": row["employee_id"],
                    "description": f"{row['employee_name']} {component}",
                    "amount": float(amount_series.loc[row.name]),
                    "employee_id": row["employee_id"],
                    "employee_name": row["employee_name"],
                    "cost_component": component,
                }
            )

    add_records(merged, "salary_account_code", merged["base_salary"], "salary")

    si_amt = merged["base_salary"] * pd.to_numeric(merged["social_insurance_rate"], errors="coerce").fillna(0.0)
    add_records(merged[merged["social_insurance_flag"] == 1], "social_insurance_account_code", si_amt, "social_insurance")

    hf_amt = merged["base_salary"] * pd.to_numeric(merged["housing_fund_rate"], errors="coerce").fillna(0.0)
    add_records(merged[merged["housing_fund_flag"] == 1], "housing_fund_account_code", hf_amt, "housing_fund")

    tax_amt = merged["base_salary"] * pd.to_numeric(merged["employer_tax_rate"], errors="coerce").fillna(0.0)
    add_records(merged[merged["employer_tax_flag"] == 1], "employer_tax_account_code", tax_amt, "employer_tax")

    if medical_rules_df is not None and not medical_rules_df.empty:
        med = medical_rules_df[["location", "monthly_medical_cost", "medical_account_code"]].copy()
        med_merge = merged.merge(med, on="location", how="left")
        med_amt = pd.to_numeric(med_merge["monthly_medical_cost"], errors="coerce").fillna(0.0)
        add_records(med_merge[med_merge["medical_flag"] == 1], "medical_account_code", med_amt, "medical")

    if bonus_rules_df is not None and not bonus_rules_df.empty:
        bonus = bonus_rules_df.copy()
        bonus["bonus_month"] = bonus["bonus_month"].map(_month_period)
        formula_col_available = "bonus_formula_type" in merged.columns

        for _, row in merged.iterrows():
            emp_rules = pd.DataFrame()
            if formula_col_available and pd.notna(row.get("bonus_formula_type")):
                emp_rules = bonus[bonus.get("bonus_formula_type") == row.get("bonus_formula_type")]
            if emp_rules.empty:
                emp_rules = bonus[(bonus["level"] == row["level"]) & (bonus["role_type"] == row["role_type"])]

            month_rules = emp_rules[emp_rules["bonus_month"] == row["month"]]
            for _, rule in month_rules.iterrows():
                amt = row["base_salary"] * float(rule["bonus_rate"])
                if pd.notna(rule["bonus_account_code"]) and amt != 0:
                    records.append(
                        {
                            "scenario_id": row["scenario_id"],
                            "entity_id": row["entity_id"],
                            "month": row["month"].strftime("%Y-%m"),
                            "account_code": rule["bonus_account_code"],
                            "posting_type": "expense",
                            "source_module": "personnel",
                            "reference_id": row["employee_id"],
                            "description": f"{row['employee_name']} bonus",
                            "amount": float(amt),
                            "employee_id": row["employee_id"],
                            "employee_name": row["employee_name"],
                            "cost_component": "bonus",
                        }
                    )

    if not records:
        return pd.DataFrame(columns=PERSONNEL_OUTPUT_COLUMNS)
    out = pd.DataFrame.from_records(records)
    return out[PERSONNEL_OUTPUT_COLUMNS].sort_values(["scenario_id", "entity_id", "employee_id", "month", "cost_component"]).reset_index(drop=True)


def build_monthly_headcount(employees_df: pd.DataFrame, start_month: str, end_month: str) -> pd.DataFrame:
    active = _active_employee_months(employees_df, start_month, end_month)
    if active.empty:
        return pd.DataFrame(columns=HEADCOUNT_OUTPUT_COLUMNS)

    out = (
        active.groupby(["scenario_id", "entity_id", "month", "role_type"], as_index=False)["employee_id"]
        .nunique()
        .rename(columns={"employee_id": "active_headcount"})
    )
    out["month"] = out["month"].dt.strftime("%Y-%m")
    return out[HEADCOUNT_OUTPUT_COLUMNS].sort_values(["scenario_id", "entity_id", "month", "role_type"]).reset_index(drop=True)
