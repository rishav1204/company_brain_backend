from app.modules.erp.vouchers.constants import VOUCHER_TYPE_PREFIX


def test_voucher_prefix_format() -> None:
    assert VOUCHER_TYPE_PREFIX["sales"] == "SAL"
    assert VOUCHER_TYPE_PREFIX["purchase"] == "PUR"
    assert VOUCHER_TYPE_PREFIX["journal"] == "JRN"


def test_sequence_service_fy_format(monkeypatch) -> None:
    from app.modules.erp.vouchers.services import voucher_sequence_service as mod

    class FakeSeqRepo:
        def next_sequence(self, org_id, voucher_type, financial_year, company_id=None):
            return 42

    monkeypatch.setattr(mod, "voucher_sequence_repository", FakeSeqRepo())
    number = mod.voucher_sequence_service.allocate_number(
        "org", voucher_type="sales", voucher_date="2026-04-01", company_id=None
    )
    assert number == "SAL/2026/000042"
