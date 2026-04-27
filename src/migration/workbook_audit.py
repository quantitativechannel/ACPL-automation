from __future__ import annotations

from typing import Any

import pandas as pd

from src.migration.legacy_parser import (
    classify_sheet_name,
    detect_broken_ref_formulas,
    detect_external_link_formulas,
    extract_actual_entity_sheets,
    extract_budget_entity_sheets,
    extract_cashflow_sheets,
    load_workbook_safe,
    summarize_sheet_dependencies,
)


def export_migration_audit_report(workbook_path: str) -> dict[str, Any]:
    wb = load_workbook_safe(workbook_path)

    sheet_summary = summarize_sheet_dependencies(wb)

    external_links_parts = []
    broken_refs_parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        external_links_parts.append(detect_external_link_formulas(ws))
        broken_refs_parts.append(detect_broken_ref_formulas(ws))

    external_links = pd.concat(external_links_parts, ignore_index=True) if external_links_parts else pd.DataFrame()
    broken_refs = pd.concat(broken_refs_parts, ignore_index=True) if broken_refs_parts else pd.DataFrame()

    budget_sheets = extract_budget_entity_sheets(wb)
    actual_sheets = extract_actual_entity_sheets(wb)
    cashflow_sheets = extract_cashflow_sheets(wb)
    driver_sheets = [
        s for s in wb.sheetnames if classify_sheet_name(s).startswith("driver_")
    ]

    notes = [
        f"Detected {len(budget_sheets)} budget entity sheets: {', '.join(budget_sheets) if budget_sheets else 'none'}.",
        f"Detected {len(actual_sheets)} actual entity sheets: {', '.join(actual_sheets) if actual_sheets else 'none'}.",
        f"Detected {len(cashflow_sheets)} cashflow/treasury sheets: {', '.join(cashflow_sheets) if cashflow_sheets else 'none'}.",
        f"Detected driver-like sheets: {', '.join(driver_sheets) if driver_sheets else 'none'}.",
        "External workbook links found." if not external_links.empty else "No external workbook links detected.",
        "Broken #REF! formulas found." if not broken_refs.empty else "No broken #REF! formulas detected.",
    ]

    high_risk = sheet_summary[
        (sheet_summary["external_link_formula_count"] > 0)
        | (sheet_summary["broken_ref_formula_count"] > 0)
        | (sheet_summary["formula_cell_count"] > 200)
    ]["sheet_name"].tolist()
    notes.append(
        f"High migration risk sheets: {', '.join(high_risk) if high_risk else 'none (based on formula/link/ref thresholds)'}.")

    return {
        "sheet_summary": sheet_summary,
        "external_links": external_links,
        "broken_refs": broken_refs,
        "notes": notes,
    }


def render_audit_markdown(audit_result: dict[str, Any]) -> str:
    sheet_summary = audit_result["sheet_summary"]
    external_links = audit_result["external_links"]
    broken_refs = audit_result["broken_refs"]
    notes = audit_result["notes"]

    total_sheets = len(sheet_summary)
    total_formula_cells = int(sheet_summary["formula_cell_count"].sum()) if total_sheets else 0

    type_counts = (
        sheet_summary.groupby("sheet_type")["sheet_name"].count().sort_values(ascending=False)
        if total_sheets
        else pd.Series(dtype=int)
    )

    lines = [
        "# Legacy Workbook Migration Audit",
        "",
        "## Workbook Overview",
        f"- Total sheets: **{total_sheets}**",
        f"- Total formula cells: **{total_formula_cells}**",
        f"- External link formulas: **{len(external_links)}**",
        f"- Broken `#REF!` formulas: **{len(broken_refs)}**",
        "",
        "## Sheet Classification Summary",
    ]

    if type_counts.empty:
        lines.append("- No sheets available.")
    else:
        for sheet_type, count in type_counts.items():
            lines.append(f"- `{sheet_type}`: {int(count)}")

    lines.extend(["", "## External Link Summary"])
    if external_links.empty:
        lines.append("- No external workbook formulas detected.")
    else:
        by_sheet = external_links.groupby("sheet_name")["cell"].count().sort_values(ascending=False)
        for sheet_name, count in by_sheet.items():
            lines.append(f"- `{sheet_name}`: {int(count)} external link formulas")

    lines.extend(["", "## Broken Reference Summary"])
    if broken_refs.empty:
        lines.append("- No broken `#REF!` formulas detected.")
    else:
        by_sheet = broken_refs.groupby("sheet_name")["cell"].count().sort_values(ascending=False)
        for sheet_name, count in by_sheet.items():
            lines.append(f"- `{sheet_name}`: {int(count)} broken reference formulas")

    lines.extend(["", "## Migration Recommendations"])
    for note in notes:
        lines.append(f"- {note}")

    lines.append("")
    lines.append("Prioritize replacing external dependencies and repairing broken references before logic translation.")

    return "\n".join(lines)
