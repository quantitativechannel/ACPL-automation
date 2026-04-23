from __future__ import annotations

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
