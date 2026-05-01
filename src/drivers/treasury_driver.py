from __future__ import annotations

import pandas as pd

_OUTPUT_COLUMNS = [
    "entity_id",
    "month",
    "opening_cash",
    "operating_inflow",
    "operating_outflow",
    "manual_net_cashflow",
    "injections",
    "transfer_in",
    "transfer_out",
    "closing_cash",
]

_GROUP_OUTPUT_COLUMNS = [
    "month",
    "opening_cash",
    "operating_inflow",
    "operating_outflow",
    "manual_net_cashflow",
    "injections",
    "transfer_in",
    "transfer_out",
    "closing_cash",
]


def _month_range(start_month: str, end_month: str) -> pd.PeriodIndex:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("end_month must be greater than or equal to start_month")
    return pd.period_range(start=start, end=end, freq="M")


def _normalize_month(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M")


def build_treasury_rollforward(
    opening_cash_df: pd.DataFrame,
    operating_cashflow_df: pd.DataFrame,
    start_month: str,
    end_month: str,
    manual_cashflow_df: pd.DataFrame | None = None,
    transfers_df: pd.DataFrame | None = None,
    injections_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    months = _month_range(start_month, end_month)

    opening = opening_cash_df.copy()
    operating = operating_cashflow_df.copy()

    opening["month"] = _normalize_month(opening["month"])
    operating["month"] = _normalize_month(operating["month"])

    entities = sorted(set(opening["entity_id"]).union(set(operating["entity_id"])))
    if manual_cashflow_df is not None and not manual_cashflow_df.empty:
        entities = sorted(set(entities).union(set(manual_cashflow_df["entity_id"])))
    if injections_df is not None and not injections_df.empty:
        entities = sorted(set(entities).union(set(injections_df["entity_id"])))
    if transfers_df is not None and not transfers_df.empty:
        entities = sorted(
            set(entities)
            .union(set(transfers_df["from_entity_id"]))
            .union(set(transfers_df["to_entity_id"]))
        )

    base = pd.MultiIndex.from_product([entities, months], names=["entity_id", "month"]).to_frame(index=False)

    opening = opening[["entity_id", "month", "opening_cash"]].copy()
    opening["opening_cash"] = pd.to_numeric(opening["opening_cash"], errors="coerce").fillna(0.0)
    opening = opening.groupby(["entity_id", "month"], as_index=False)["opening_cash"].last()

    operating = operating[["entity_id", "month", "operating_inflow", "operating_outflow"]].copy()
    operating["operating_inflow"] = pd.to_numeric(operating["operating_inflow"], errors="coerce").fillna(0.0)
    operating["operating_outflow"] = pd.to_numeric(operating["operating_outflow"], errors="coerce").fillna(0.0)
    operating = operating.groupby(["entity_id", "month"], as_index=False)[["operating_inflow", "operating_outflow"]].sum()

    df = base.merge(opening, on=["entity_id", "month"], how="left")
    df = df.merge(operating, on=["entity_id", "month"], how="left")

    if manual_cashflow_df is not None and not manual_cashflow_df.empty:
        manual = manual_cashflow_df.copy()
        manual["month"] = _normalize_month(manual["month"])
        manual["amount"] = pd.to_numeric(manual["amount"], errors="coerce").fillna(0.0)
        manual = manual.groupby(["entity_id", "month"], as_index=False)["amount"].sum()
        manual = manual.rename(columns={"amount": "manual_net_cashflow"})
        df = df.merge(manual, on=["entity_id", "month"], how="left")
    else:
        df["manual_net_cashflow"] = 0.0

    if injections_df is not None and not injections_df.empty:
        injections = injections_df.copy()
        injections["month"] = _normalize_month(injections["month"])
        injections["amount"] = pd.to_numeric(injections["amount"], errors="coerce").fillna(0.0)
        injections = injections.groupby(["entity_id", "month"], as_index=False)["amount"].sum()
        injections = injections.rename(columns={"amount": "injections"})
        df = df.merge(injections, on=["entity_id", "month"], how="left")
    else:
        df["injections"] = 0.0

    if transfers_df is not None and not transfers_df.empty:
        transfers = transfers_df.copy()
        transfers["month"] = _normalize_month(transfers["month"])
        transfers["amount"] = pd.to_numeric(transfers["amount"], errors="coerce").fillna(0.0)

        transfer_out = (
            transfers.groupby(["from_entity_id", "month"], as_index=False)["amount"].sum()
            .rename(columns={"from_entity_id": "entity_id", "amount": "transfer_out"})
        )
        transfer_in = (
            transfers.groupby(["to_entity_id", "month"], as_index=False)["amount"].sum()
            .rename(columns={"to_entity_id": "entity_id", "amount": "transfer_in"})
        )

        df = df.merge(transfer_in, on=["entity_id", "month"], how="left")
        df = df.merge(transfer_out, on=["entity_id", "month"], how="left")
    else:
        df["transfer_in"] = 0.0
        df["transfer_out"] = 0.0

    for col in [
        "opening_cash",
        "operating_inflow",
        "operating_outflow",
        "manual_net_cashflow",
        "injections",
        "transfer_in",
        "transfer_out",
    ]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")

    rows: list[dict[str, float | str]] = []
    for entity_id, entity_rows in df.sort_values(["entity_id", "month"]).groupby("entity_id", sort=False):
        carried_opening = 0.0
        for _, row in entity_rows.iterrows():
            if pd.notna(row["opening_cash"]):
                opening_cash = float(row["opening_cash"])
            else:
                opening_cash = carried_opening

            closing_cash = (
                opening_cash
                + float(row["operating_inflow"] if pd.notna(row["operating_inflow"]) else 0.0)
                - float(row["operating_outflow"] if pd.notna(row["operating_outflow"]) else 0.0)
                + float(row["manual_net_cashflow"] if pd.notna(row["manual_net_cashflow"]) else 0.0)
                + float(row["injections"] if pd.notna(row["injections"]) else 0.0)
                + float(row["transfer_in"] if pd.notna(row["transfer_in"]) else 0.0)
                - float(row["transfer_out"] if pd.notna(row["transfer_out"]) else 0.0)
            )

            rows.append(
                {
                    "entity_id": entity_id,
                    "month": str(row["month"]),
                    "opening_cash": opening_cash,
                    "operating_inflow": float(row["operating_inflow"] if pd.notna(row["operating_inflow"]) else 0.0),
                    "operating_outflow": float(row["operating_outflow"] if pd.notna(row["operating_outflow"]) else 0.0),
                    "manual_net_cashflow": float(row["manual_net_cashflow"] if pd.notna(row["manual_net_cashflow"]) else 0.0),
                    "injections": float(row["injections"] if pd.notna(row["injections"]) else 0.0),
                    "transfer_in": float(row["transfer_in"] if pd.notna(row["transfer_in"]) else 0.0),
                    "transfer_out": float(row["transfer_out"] if pd.notna(row["transfer_out"]) else 0.0),
                    "closing_cash": closing_cash,
                }
            )
            carried_opening = closing_cash

    return pd.DataFrame(rows, columns=_OUTPUT_COLUMNS)


def build_group_treasury_rollforward(rollforward_df: pd.DataFrame) -> pd.DataFrame:
    if rollforward_df.empty:
        return pd.DataFrame(columns=_GROUP_OUTPUT_COLUMNS)

    grouped = (
        rollforward_df.groupby("month", as_index=False)[
            [
                "opening_cash",
                "operating_inflow",
                "operating_outflow",
                "manual_net_cashflow",
                "injections",
                "transfer_in",
                "transfer_out",
                "closing_cash",
            ]
        ]
        .sum()
        .sort_values("month")
        .reset_index(drop=True)
    )
    return grouped[_GROUP_OUTPUT_COLUMNS]
