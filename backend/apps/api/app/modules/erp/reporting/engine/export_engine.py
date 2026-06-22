from __future__ import annotations

import csv
import io
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def export_csv(report_type: str, payload: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["report_type", report_type])
    if report_type == "trial_balance":
        writer.writerow(["account_code", "account_name", "debit_total", "credit_total", "balance"])
        for line in payload.get("lines") or []:
            writer.writerow([
                line.get("account_code"),
                line.get("account_name"),
                line.get("debit_total"),
                line.get("credit_total"),
                line.get("balance"),
            ])
    elif report_type in {"ap_aging", "ar_aging"}:
        writer.writerow(["entity_id", "entity_name", "current", "1-30", "31-60", "61-90", "90+", "total"])
        for line in payload.get("lines") or []:
            writer.writerow([
                line.get("entity_id"),
                line.get("entity_name"),
                line.get("bucket_current"),
                line.get("bucket_1_30"),
                line.get("bucket_31_60"),
                line.get("bucket_61_90"),
                line.get("bucket_90_plus"),
                line.get("total_outstanding"),
            ])
    else:
        writer.writerow(["data"])
        writer.writerow([json.dumps(payload)])
    return buffer.getvalue().encode("utf-8")


def export_pdf(report_type: str, payload: dict, *, title: str | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(title or f"ERP Report — {report_type}", styles["Title"]))
    story.append(Spacer(1, 6 * mm))

    if report_type == "trial_balance":
        rows = [["Code", "Account", "Debit", "Credit", "Balance"]]
        for line in payload.get("lines") or []:
            rows.append([
                str(line.get("account_code") or ""),
                str(line.get("account_name") or ""),
                f"{float(line.get('debit_total') or 0):,.2f}",
                f"{float(line.get('credit_total') or 0):,.2f}",
                f"{float(line.get('balance') or 0):,.2f}",
            ])
    elif report_type in {"pnl", "balance_sheet"}:
        rows = [["Category", "Amount"]]
        for line in payload.get("sections") or payload.get("lines") or []:
            rows.append([str(line.get("reporting_category") or ""), f"{float(line.get('amount') or 0):,.2f}"])
    else:
        rows = [["Field", "Value"]]
        for k, v in (payload.get("totals") or payload).items():
            if isinstance(v, (dict, list)):
                continue
            rows.append([str(k), str(v)])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def export_excel(report_type: str, payload: dict) -> bytes:
    try:
        import openpyxl
    except ImportError:
        raise ValueError("openpyxl required for Excel export")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = report_type[:31]
    ws.append(["report_type", report_type])
    if report_type == "trial_balance":
        ws.append(["account_code", "account_name", "debit_total", "credit_total", "balance"])
        for line in payload.get("lines") or []:
            ws.append([
                line.get("account_code"),
                line.get("account_name"),
                line.get("debit_total"),
                line.get("credit_total"),
                line.get("balance"),
            ])
    else:
        ws.append(["payload"])
        ws.append([json.dumps(payload)])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def render_export(report_type: str, payload: dict, *, fmt: str) -> tuple[bytes, str]:
    fmt = (fmt or "csv").lower()
    if fmt == "pdf":
        return export_pdf(report_type, payload), "application/pdf"
    if fmt in {"xlsx", "excel"}:
        return export_excel(report_type, payload), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return export_csv(report_type, payload), "text/csv"
