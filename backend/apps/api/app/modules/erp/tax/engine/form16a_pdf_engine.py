from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet


def render_form16a_pdf(payload: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Form 16A — Certificate of Tax Deducted at Source", styles["Title"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(f"Deductee: {payload.get('vendor_name') or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"PAN: {payload.get('pan') or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"Financial Year: {payload.get('financial_year')} | Quarter: {payload.get('quarter')}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    rows = [["Section", "Gross Amount", "TDS Amount", "Deduction Date"]]
    for item in payload.get("deductions") or []:
        rows.append([
            str(item.get("section_code") or ""),
            f"{float(item.get('gross_amount') or 0):,.2f}",
            f"{float(item.get('tds_amount') or 0):,.2f}",
            str(item.get("deduction_date") or ""),
        ])
    rows.append(["Total", f"{float(payload.get('gross_total') or 0):,.2f}", f"{float(payload.get('tds_total') or 0):,.2f}", ""])

    table = Table(rows, colWidths=[35 * mm, 45 * mm, 45 * mm, 45 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(table)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("This is a system-generated certificate. Verify against books before issuance.", styles["Italic"]))

    doc.build(story)
    return buffer.getvalue()
