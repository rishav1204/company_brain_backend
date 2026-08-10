from __future__ import annotations



from datetime import datetime, timezone



from app.modules.erp.tax.events.tax_events import emit_irn_generated

from app.modules.erp.tax.repositories.compliance_repository import e_invoice_repository

from app.modules.erp.tax.repositories.gst_repository import gst_registration_repository

from app.modules.platform.integrations.connectors.gst.gst_connector_resolver import resolve_irp_connector





class EInvoiceService:

    def _registration_settings(self, org_id: str) -> dict:

        reg = gst_registration_repository.get_primary(org_id) or {}

        meta = reg.get("metadata") if isinstance(reg.get("metadata"), dict) else {}

        return {

            "auto_einvoice": bool(meta.get("auto_einvoice", True)),

            "einvoice_threshold": float(meta.get("einvoice_threshold", 0)),

            "require_workflow": bool(meta.get("einvoice_workflow", False)),

        }



    def _writeback_irn(self, org_id: str, *, ar_invoice_id: str, irn: str, qr_code: str | None, ack_no: str | None) -> None:

        from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository



        inv = ar_invoice_repository.get(org_id, invoice_id=ar_invoice_id) or {}

        meta = inv.get("metadata") if isinstance(inv.get("metadata"), dict) else {}

        meta.update({"irn": irn, "qr_code": qr_code, "ack_no": ack_no, "e_invoice_status": "generated"})

        ar_invoice_repository.update_metadata(org_id, invoice_id=ar_invoice_id, metadata=meta)



    def generate(self, org_id: str, *, ar_invoice_id: str, skip_workflow: bool = False) -> dict:

        existing = e_invoice_repository.get_by_invoice(org_id, ar_invoice_id=ar_invoice_id)

        if existing and existing.get("irn"):

            return existing

        from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

        from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository



        inv = ar_invoice_repository.get(org_id, invoice_id=ar_invoice_id)

        if not inv:

            raise ValueError("AR invoice not found")

        # INT-07: IRN generation must require a posted invoice (journal posted).
        jid = str(inv.get("journal_id") or "").strip()
        if not jid:
            raise ValueError("E-invoice requires AR invoice to be issued and posted (missing journal_id)")
        try:
            from app.modules.erp.journals.repositories.journal_repository import journal_repository

            j = journal_repository.get(org_id, journal_id=jid) or {}
            if str(j.get("journal_status")) != "posted":
                raise ValueError("E-invoice requires AR invoice journal to be posted")
        except ValueError:
            raise
        except Exception:
            # Fail closed: do not generate if we cannot verify posting state.
            raise ValueError("E-invoice requires posted AR invoice (unable to verify journal status)")

        settings = self._registration_settings(org_id)

        if settings["require_workflow"] and not skip_workflow:

            return self.submit_for_approval(org_id, ar_invoice_id=ar_invoice_id, started_by=None)



        customer = customer_repository.get(org_id, customer_id=str(inv.get("customer_id") or "")) or {}

        connector = resolve_irp_connector()

        if not connector or not hasattr(connector, "generate_irn"):

            raise ValueError("IRP connector not available")

        result = connector.generate_irn(

            idempotency_key=f"{org_id}:{ar_invoice_id}",

            payload={

                "invoice_number": inv.get("invoice_number"),

                "total_amount": float(inv.get("total_amount") or 0),

                "gst_amount": float(inv.get("gst_amount") or 0),

                "customer_gstin": customer.get("gstin"),

            },

        )

        if hasattr(result, "irn"):

            irn = result.irn

            ack_no = result.ack_no

            ack_date = result.ack_date

            qr_code = result.qr_code

            raw = result.raw or {}

        else:

            irn = result.get("irn")

            ack_no = result.get("ack_no")

            ack_date = result.get("ack_date")

            qr_code = result.get("qr_code")

            raw = result

        row = e_invoice_repository.create(

            org_id,

            ar_invoice_id=ar_invoice_id,

            irn=irn,

            ack_no=ack_no,

            ack_date=ack_date,

            qr_code=qr_code,

            status="generated",

            raw_response=raw if isinstance(raw, dict) else {"result": raw},

        )

        self._writeback_irn(org_id, ar_invoice_id=ar_invoice_id, irn=str(irn or ""), qr_code=qr_code, ack_no=ack_no)

        emit_irn_generated(org_id, e_invoice_id=str(row["id"]), irn=str(irn or ""), ar_invoice_id=ar_invoice_id)

        return row



    def maybe_auto_generate(self, org_id: str, *, ar_invoice_id: str) -> dict | None:

        settings = self._registration_settings(org_id)

        if not settings["auto_einvoice"]:

            return None

        from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

        from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository



        inv = ar_invoice_repository.get(org_id, invoice_id=ar_invoice_id)

        if not inv:

            return None

        customer = customer_repository.get(org_id, customer_id=str(inv.get("customer_id") or "")) or {}

        if not customer.get("gstin"):

            return None

        total = float(inv.get("total_amount") or 0)

        if total < settings["einvoice_threshold"]:

            return None

        return self.generate(org_id, ar_invoice_id=ar_invoice_id)



    def submit_for_approval(self, org_id: str, *, ar_invoice_id: str, started_by: str | None) -> dict:

        try:

            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created



            handle_entity_created(

                org_id=org_id,

                payload={

                    "entity_type": "e_invoice",

                    "entity_id": ar_invoice_id,

                    "workflow_key": "EINVOICE_GENERATION",

                    "started_by": started_by,

                    "metadata": {"ar_invoice_id": ar_invoice_id},

                },

            )

        except Exception:

            return self.generate(org_id, ar_invoice_id=ar_invoice_id, skip_workflow=True)

        row = e_invoice_repository.create(org_id, ar_invoice_id=ar_invoice_id, status="pending_approval")

        return row



    def mark_workflow_approved(self, org_id: str, *, ar_invoice_id: str) -> dict:

        return self.generate(org_id, ar_invoice_id=ar_invoice_id, skip_workflow=True)



    def cancel(self, org_id: str, *, ar_invoice_id: str, reason: str = "") -> dict:

        row = e_invoice_repository.get_by_invoice(org_id, ar_invoice_id=ar_invoice_id)

        if not row or not row.get("irn"):

            raise ValueError("E-invoice IRN not found")

        connector = resolve_irp_connector()

        if connector and hasattr(connector, "cancel_irn"):

            connector.cancel_irn(irn=str(row["irn"]), reason=reason)

        return e_invoice_repository.create(org_id, ar_invoice_id=ar_invoice_id, irn=None, status="cancelled")



    def get(self, org_id: str, *, ar_invoice_id: str) -> dict | None:

        return e_invoice_repository.get_by_invoice(org_id, ar_invoice_id=ar_invoice_id)





e_invoice_service = EInvoiceService()

