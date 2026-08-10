from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.mapping_repository import mapping_repository
from app.modules.erp.reporting.services.trial_balance_service import trial_balance_service


_CASH_ACCOUNT_TYPES = frozenset({"bank", "cash", "cash_equivalent"})
_STATUTORY_LINES = (
    ("net_profit_before_tax", "operating"),
    ("depreciation_amortization", "operating"),
    ("working_capital_change", "operating"),
    ("cash_from_operations", "operating"),
    ("capex", "investing"),
    ("cash_from_investing", "investing"),
    ("loan_proceeds", "financing"),
    ("loan_repayments", "financing"),
    ("cash_from_financing", "financing"),
)


class CashFlowService:
    def get(self, org_id: str, *, fiscal_period_id: str | None = None) -> dict:
        if not fiscal_period_id:
            return {"status": "error", "detail": "fiscal_period_id required", "sections": []}

        tb = trial_balance_service.get_from_reporting(org_id, fiscal_period_id=fiscal_period_id, limit=5000)
        lines = tb.get("lines") or []
        accounts = {str(a["id"]): a for a in account_repository.list(org_id, limit=5000)}
        fin_map = {
            str(m.get("account_id")): str(m.get("reporting_category") or "").lower()
            for m in mapping_repository.list_financial_mappings(org_id, limit=500)
        }

        operating: list[dict] = []
        investing: list[dict] = []
        financing: list[dict] = []
        opening_cash = 0.0
        closing_cash = 0.0
        cash_movement = 0.0

        for row in lines:
            aid = str(row.get("account_id") or "")
            acc = accounts.get(aid) or {}
            acc_type = str(acc.get("account_type") or "").lower()
            opening = float(row.get("opening_balance") or 0)
            closing = float(row.get("closing_balance") or 0)
            debit = float(row.get("debit_total") or 0)
            credit = float(row.get("credit_total") or 0)
            net = round(debit - credit, 2)
            entry = {
                "account_id": aid,
                "account_code": row.get("account_code") or acc.get("account_code"),
                "account_name": row.get("account_name") or acc.get("account_name"),
                "net_movement": net,
                "opening_balance": round(opening, 2),
                "closing_balance": round(closing, 2),
                "reporting_category": fin_map.get(aid),
            }
            if acc_type in _CASH_ACCOUNT_TYPES:
                opening_cash += opening
                closing_cash += closing
                cash_movement += net
                continue
            category = fin_map.get(aid) or str((acc.get("group_name") or acc_type or "operating")).lower()
            if any(k in category for k in ("fixed", "asset", "investment", "capex")):
                investing.append(entry)
            elif any(k in category for k in ("loan", "equity", "capital", "borrowing", "finance")):
                financing.append(entry)
            else:
                operating.append(entry)

        sections = [
            {"name": "operating", "items": operating, "total": round(sum(i["net_movement"] for i in operating), 2)},
            {"name": "investing", "items": investing, "total": round(sum(i["net_movement"] for i in investing), 2)},
            {"name": "financing", "items": financing, "total": round(sum(i["net_movement"] for i in financing), 2)},
        ]
        net_change = round(sum(s["total"] for s in sections), 2)
        statutory_lines: dict[str, dict] = {}
        for line_key, section_name in _STATUTORY_LINES:
            section = next((s for s in sections if s["name"] == section_name), None)
            if not section:
                continue
            if line_key.endswith("_from_operations") or line_key.endswith("_from_investing") or line_key.endswith("_from_financing"):
                statutory_lines[line_key] = {"amount": section["total"], "section": section_name}
            elif line_key == "net_profit_before_tax":
                statutory_lines[line_key] = {
                    "amount": round(sum(i["net_movement"] for i in operating), 2),
                    "section": "operating",
                }
            elif line_key == "depreciation_amortization":
                dep = sum(
                    i["net_movement"]
                    for i in operating
                    if "deprec" in str(i.get("account_name") or "").lower()
                    or "amort" in str(i.get("account_name") or "").lower()
                )
                statutory_lines[line_key] = {"amount": round(dep, 2), "section": "operating"}
            elif line_key == "working_capital_change":
                wc = round(section["total"] - statutory_lines.get("net_profit_before_tax", {}).get("amount", 0), 2)
                statutory_lines[line_key] = {"amount": wc, "section": "operating"}
            elif line_key == "capex":
                capex = sum(
                    i["net_movement"]
                    for i in investing
                    if any(k in str(i.get("reporting_category") or i.get("account_name") or "").lower() for k in ("fixed", "capex", "plant"))
                )
                statutory_lines[line_key] = {"amount": round(capex, 2), "section": "investing"}
            elif line_key in {"loan_proceeds", "loan_repayments"}:
                loan_items = [
                    i for i in financing
                    if any(k in str(i.get("reporting_category") or i.get("account_name") or "").lower() for k in ("loan", "borrowing"))
                ]
                amt = round(sum(i["net_movement"] for i in loan_items), 2)
                if line_key == "loan_repayments":
                    amt = round(-abs(amt), 2) if amt > 0 else amt
                statutory_lines[line_key] = {"amount": amt, "section": "financing"}

        return {
            "status": "ok",
            "method": "indirect_statutory",
            "format": "schedule_iii_indirect",
            "fiscal_period_id": fiscal_period_id,
            "sections": sections,
            "statutory_lines": statutory_lines,
            "statutory_summary": {
                "opening_cash": round(opening_cash, 2),
                "closing_cash": round(closing_cash, 2),
                "net_cash_change": net_change,
                "cash_account_movement": round(cash_movement, 2),
                "reconciled": abs((opening_cash + net_change) - closing_cash) < 0.05,
            },
            "balanced_to_cash": abs(net_change - cash_movement) < 0.05,
        }


cash_flow_service = CashFlowService()
