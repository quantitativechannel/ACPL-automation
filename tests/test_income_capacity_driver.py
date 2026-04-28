import pandas as pd

from src.drivers.income_capacity_driver import build_capacity_rollforward


def test_month_end_capacity_rollforward() -> None:
    assumptions = pd.DataFrame(
        [
            {
                "scenario_id": "Base",
                "project_group": "F",
                "month": "2026-01",
                "new_capacity_w": 100,
                "addition_timing_factor": 1,
                "avg_equity_price_per_w": 2,
            },
            {
                "scenario_id": "Base",
                "project_group": "F",
                "month": "2026-02",
                "new_capacity_w": 200,
                "addition_timing_factor": 1,
                "avg_equity_price_per_w": 2,
            },
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-02", initial_capacity_w=50)

    assert result["month_end_capacity_w"].tolist() == [150, 350]


def test_weighted_average_capacity_timing_factors() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "F", "month": "2026-01", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-02", "new_capacity_w": 100, "addition_timing_factor": 0.5, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-03", "new_capacity_w": 100, "addition_timing_factor": 0, "avg_equity_price_per_w": 0},
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-03", initial_capacity_w=200)

    jan, feb, mar = result["weighted_avg_capacity_w"].tolist()
    assert jan == 300
    assert feb == 350
    assert mar == 400


def test_new_project_count_uses_ceil() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "F", "month": "2026-01", "new_capacity_w": 0, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-02", "new_capacity_w": 101, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-02")

    assert result["new_project_count"].tolist() == [0, 2]


def test_region_count_rules() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "F", "month": "2026-01", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-02", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-03", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-04", "new_capacity_w": 400, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-04")

    assert result["month_end_project_count"].tolist() == [1, 2, 3, 7]
    assert result["month_end_region_count"].tolist() == [1, 2, 3, 4]


def test_manual_project_count_override() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "F", "month": "2026-01", "new_capacity_w": 250, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {
                "scenario_id": "Base",
                "project_group": "F",
                "month": "2026-02",
                "new_capacity_w": 250,
                "addition_timing_factor": 1,
                "avg_equity_price_per_w": 0,
                "manual_project_count_override": 10,
            },
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-02")

    assert result["new_project_count"].tolist() == [3, 3]
    assert result["month_end_project_count"].tolist() == [3, 10]


def test_manual_region_count_override() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "F", "month": "2026-01", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {
                "scenario_id": "Base",
                "project_group": "F",
                "month": "2026-02",
                "new_capacity_w": 0,
                "addition_timing_factor": 0,
                "avg_equity_price_per_w": 0,
                "manual_region_count_override": 9,
            },
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-02")

    assert result["month_end_region_count"].tolist() == [1, 9]


def test_jv_equity_contribution_rollforward() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "F", "month": "2026-01", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 2},
            {"scenario_id": "Base", "project_group": "F", "month": "2026-02", "new_capacity_w": 200, "addition_timing_factor": 1, "avg_equity_price_per_w": 3},
        ]
    )

    result = build_capacity_rollforward(
        assumptions,
        "2026-01",
        "2026-02",
        initial_jv_equity_contribution=50,
    )

    assert result["jv_equity_new_contribution"].tolist() == [200, 600]
    assert result["jv_equity_cumulative_contribution"].tolist() == [250, 850]


def test_multiple_project_group_support() -> None:
    assumptions = pd.DataFrame(
        [
            {"scenario_id": "Base", "project_group": "A", "month": "2026-01", "new_capacity_w": 100, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
            {"scenario_id": "Base", "project_group": "B", "month": "2026-01", "new_capacity_w": 200, "addition_timing_factor": 1, "avg_equity_price_per_w": 0},
        ]
    )

    result = build_capacity_rollforward(assumptions, "2026-01", "2026-01")

    by_group = result.set_index("project_group")["month_end_capacity_w"].to_dict()
    assert by_group == {"A": 100, "B": 200}
