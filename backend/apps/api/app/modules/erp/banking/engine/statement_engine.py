from __future__ import annotations

import csv
import io
import re
from typing import Any


def parse_csv_statement(content: str, *, column_map: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Parse CSV bank statement into canonical rows."""
    col = column_map or {"date": "date", "amount": "amount", "type": "type", "reference": "reference", "narration": "narration"}
    reader = csv.DictReader(io.StringIO(content))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        date_val = _pick(raw, col.get("date", "date"), "transaction_date", "txn date", "value date")
        amount_val = _pick(raw, col.get("amount", "amount"), "withdrawal", "deposit")
        type_val = _pick(raw, col.get("type", "type"), "dr/cr", "debit/credit")
        ref = _pick(raw, col.get("reference", "reference"), "ref", "cheque no")
        narr = _pick(raw, col.get("narration", "narration"), "description", "particulars", "remarks")
        amount = _parse_amount(amount_val, type_val, raw)
        if not date_val or amount == 0:
            continue
        tx_type = "credit" if amount > 0 else "debit"
        rows.append({
            "date": str(date_val)[:10],
            "amount": abs(amount),
            "type": tx_type,
            "reference": str(ref or "")[:128],
            "narration": str(narr or "")[:512],
        })
    return rows


def parse_mt940(content: str) -> list[dict[str, Any]]:
    """Minimal MT940 parser for :61: and :86: tags."""
    rows: list[dict[str, Any]] = []
    current_narration = ""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith(":86:"):
            current_narration = line[4:].strip()
        elif line.startswith(":61:"):
            body = line[4:]
            m = re.match(r"(\d{6})(\d{4})?([CD])([\d,]+)", body.replace(",", "."))
            if not m:
                continue
            yy, mm, dd = int(body[0:2]), int(body[2:4]), int(body[4:6])
            year = 2000 + yy if yy < 80 else 1900 + yy
            dc = m.group(3)
            amount = float(m.group(4).replace(",", ""))
            rows.append({
                "date": f"{year:04d}-{mm:02d}-{dd:02d}",
                "amount": amount,
                "type": "credit" if dc == "C" else "debit",
                "reference": body[10:26].strip() if len(body) > 10 else "",
                "narration": current_narration,
            })
            current_narration = ""
    return rows


def parse_excel_statement(content: bytes) -> list[dict[str, Any]]:
    try:
        import openpyxl
    except ImportError:
        raise ValueError("openpyxl required for Excel statement import")
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = wb.active
    headers: list[str] = []
    raw_rows: list[dict] = []
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c or "").strip().lower() for c in row]
            continue
        if not any(row):
            continue
        raw_rows.append({headers[j]: row[j] for j in range(min(len(headers), len(row))) if headers[j]})
    text = io.StringIO()
    if raw_rows:
        writer = csv.DictWriter(text, fieldnames=list(raw_rows[0].keys()))
        writer.writeheader()
        writer.writerows(raw_rows)
    return parse_csv_statement(text.getvalue())


def _pick(row: dict, *keys: str) -> str:
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _parse_amount(amount_val: str, type_val: str, raw: dict) -> float:
    if amount_val:
        try:
            amt = float(str(amount_val).replace(",", ""))
        except ValueError:
            amt = 0.0
    else:
        dep = _pick(raw, "deposit", "credit")
        wit = _pick(raw, "withdrawal", "debit")
        try:
            amt = float(dep or 0) - float(wit or 0)
        except ValueError:
            amt = 0.0
    t = type_val.lower()
    if t in {"cr", "credit", "c"} and amt > 0:
        return abs(amt)
    if t in {"dr", "debit", "d"} and amt > 0:
        return -abs(amt)
    return amt
