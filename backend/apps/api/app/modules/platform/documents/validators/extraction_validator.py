def validate_gst_math(data: dict) -> bool:
    subtotal = float(data.get("subtotal") or 0)
    cgst = float(data.get("cgst") or 0)
    sgst = float(data.get("sgst") or 0)
    igst = float(data.get("igst") or 0)
    cess = float(data.get("cess") or 0)
    total = float(data.get("total_amount") or 0)
    expected = round(subtotal + cgst + sgst + igst + cess, 2)
    return abs(expected - round(total, 2)) < 0.01
