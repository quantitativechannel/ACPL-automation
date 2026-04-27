BEGIN;

CREATE TABLE IF NOT EXISTS income_revenue_policies (
    policy_id INTEGER PRIMARY KEY,
    policy_name TEXT UNIQUE NOT NULL,
    revenue_type TEXT NOT NULL,
    rate REAL NOT NULL DEFAULT 0,
    vat_rate REAL NOT NULL DEFAULT 0,
    cit_rate REAL NOT NULL DEFAULT 0,
    active_flag INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS capacity_assumptions (
    row_id INTEGER PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    project_group TEXT NOT NULL,
    month TEXT NOT NULL,
    new_capacity_w REAL NOT NULL DEFAULT 0,
    addition_timing_factor REAL NOT NULL DEFAULT 0,
    avg_equity_price_per_w REAL NOT NULL DEFAULT 0.2,
    manual_project_count_override REAL,
    manual_region_count_override REAL,
    notes TEXT,
    UNIQUE (scenario_id, project_group, month)
);

CREATE TABLE IF NOT EXISTS capacity_rollforward (
    row_id INTEGER PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    project_group TEXT NOT NULL,
    month TEXT NOT NULL,
    new_capacity_w REAL NOT NULL DEFAULT 0,
    month_end_capacity_w REAL NOT NULL DEFAULT 0,
    weighted_avg_capacity_w REAL NOT NULL DEFAULT 0,
    new_project_count INTEGER NOT NULL DEFAULT 0,
    month_end_project_count INTEGER NOT NULL DEFAULT 0,
    new_region_count INTEGER NOT NULL DEFAULT 0,
    month_end_region_count INTEGER NOT NULL DEFAULT 0,
    jv_equity_new_contribution REAL NOT NULL DEFAULT 0,
    jv_equity_cumulative_contribution REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS maa_assumptions (
    row_id INTEGER PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    project_group TEXT NOT NULL,
    month TEXT NOT NULL,
    incentive_1_flag INTEGER NOT NULL DEFAULT 0,
    incentive_2_flag INTEGER NOT NULL DEFAULT 0,
    reimbursed_cost_ex_vat REAL NOT NULL DEFAULT 0,
    notes TEXT,
    UNIQUE (scenario_id, project_group, month)
);

CREATE TABLE IF NOT EXISTS revenue_allocation_rules (
    rule_id INTEGER PRIMARY KEY,
    revenue_type TEXT NOT NULL,
    recipient_entity_code TEXT NOT NULL,
    allocation_pct REAL NOT NULL DEFAULT 0,
    haircut_pct REAL NOT NULL DEFAULT 0,
    active_flag INTEGER NOT NULL DEFAULT 1,
    UNIQUE (revenue_type, recipient_entity_code)
);

CREATE TABLE IF NOT EXISTS cash_collection_rules (
    rule_id INTEGER PRIMARY KEY,
    revenue_type TEXT NOT NULL,
    collection_method TEXT NOT NULL,
    collection_months TEXT,
    settlement_month TEXT,
    active_flag INTEGER NOT NULL DEFAULT 1,
    UNIQUE (revenue_type, collection_method, collection_months, settlement_month)
);

CREATE TABLE IF NOT EXISTS fund_assumptions (
    row_id INTEGER PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    fund_name TEXT NOT NULL,
    month TEXT NOT NULL,
    initial_fund_equity_contribution REAL NOT NULL DEFAULT 0,
    fixed_expense_contribution REAL NOT NULL DEFAULT 0,
    gp_commitment_pct REAL,
    lp_commitment_pct REAL,
    management_fee_rate REAL NOT NULL DEFAULT 0,
    vat_rate REAL NOT NULL DEFAULT 0,
    cit_rate REAL NOT NULL DEFAULT 0,
    incentive_flag INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    UNIQUE (scenario_id, fund_name, month)
);

CREATE TABLE IF NOT EXISTS fund_rollforward (
    row_id INTEGER PRIMARY KEY,
    scenario_id INTEGER NOT NULL,
    fund_name TEXT NOT NULL,
    month TEXT NOT NULL,
    fund_equity_new_contribution REAL NOT NULL DEFAULT 0,
    fund_equity_cumulative_contribution REAL NOT NULL DEFAULT 0,
    fund_expense_new_contribution REAL NOT NULL DEFAULT 0,
    fund_expense_cumulative_contribution REAL NOT NULL DEFAULT 0,
    gp_new_contribution REAL NOT NULL DEFAULT 0,
    gp_cumulative_contribution REAL NOT NULL DEFAULT 0,
    lp_new_contribution REAL NOT NULL DEFAULT 0,
    lp_cumulative_contribution REAL NOT NULL DEFAULT 0,
    base_management_fee REAL NOT NULL DEFAULT 0,
    incentive_management_fee REAL NOT NULL DEFAULT 0
);

ALTER TABLE monthly_postings ADD COLUMN posting_type TEXT;
ALTER TABLE monthly_postings ADD COLUMN revenue_type TEXT;
ALTER TABLE monthly_postings ADD COLUMN counterparty TEXT;

COMMIT;
