from __future__ import annotations


class AccountValidationService:
    GROUP_TYPES = {"asset", "liability", "equity", "revenue", "expense"}
    NATURES = {"debit", "credit"}

    ACCOUNT_TYPES = {
        "cash",
        "bank",
        "receivable",
        "payable",
        "expense",
        "revenue",
        "gst_input",
        "gst_output",
        "fixed_asset",
        "depreciation",
    }

    STATEMENT_TYPES = {"balance_sheet", "profit_loss", "cash_flow"}
    GST_TYPES = {
        "cgst_input",
        "sgst_input",
        "igst_input",
        "cgst_output",
        "sgst_output",
        "igst_output",
        "reverse_charge",
    }

    def validate_group(self, *, group_type: str, nature: str) -> None:
        if group_type not in self.GROUP_TYPES:
            raise ValueError("Invalid group_type")
        if nature not in self.NATURES:
            raise ValueError("Invalid nature")
        # Accounting normal balance defaults (enforced at group creation)
        expected = {
            "asset": "debit",
            "expense": "debit",
            "liability": "credit",
            "revenue": "credit",
            "equity": "credit",
        }.get(group_type)
        if expected and nature != expected:
            raise ValueError(f"Invalid nature for group_type={group_type}. Expected {expected}.")

    def validate_account(self, *, account_type: str, is_postable: bool, parent_account_id: str | None) -> None:
        if account_type not in self.ACCOUNT_TYPES:
            raise ValueError("Invalid account_type")
        # Hierarchy rule: non-postable accounts should typically be parents.
        if not is_postable and parent_account_id:
            # allow nested non-postable, but it's unusual; keep allowed
            return

    def validate_statement_mapping(self, *, statement_type: str, reporting_category: str) -> None:
        if statement_type not in self.STATEMENT_TYPES:
            raise ValueError("Invalid statement_type")
        if not reporting_category or len(reporting_category.strip()) < 2:
            raise ValueError("Invalid reporting_category")

    def validate_gst_mapping(self, *, gst_type: str, itc_eligible: bool) -> None:
        if gst_type not in self.GST_TYPES:
            raise ValueError("Invalid gst_type")
        if "output" in gst_type and itc_eligible:
            raise ValueError("Output GST cannot be ITC eligible")

    def ensure_no_hierarchy_loop(self, *, node_id: str, parent_id: str | None, parent_chain: dict[str, str | None]) -> None:
        """
        parent_chain maps id -> parent_id for the org scope.
        Prevent loops like A->B->A.
        """
        if not parent_id:
            return
        seen = {node_id}
        cur = parent_id
        while cur:
            if cur in seen:
                raise ValueError("Hierarchy loop detected")
            seen.add(cur)
            cur = parent_chain.get(cur)

    def can_deactivate_account(self, *, has_balance: bool, used_in_journals: bool) -> None:
        if has_balance:
            raise ValueError("Cannot deactivate account with balance")
        if used_in_journals:
            raise ValueError("Cannot deactivate account used in journals")


account_validation_service = AccountValidationService()

