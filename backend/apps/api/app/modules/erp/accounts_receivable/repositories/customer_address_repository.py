from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class CustomerAddressRepository:
    def create(
        self,
        org_id: str,
        *,
        customer_id: str,
        address_type: str,
        line1: str,
        line2: str | None = None,
        city: str | None = None,
        state_code: str | None = None,
        postal_code: str | None = None,
        country_code: str = "IN",
        place_of_supply: str | None = None,
        is_primary: bool = False,
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.customer_addresses (
                      id, org_id, customer_id, address_type, line1, line2, city,
                      state_code, postal_code, country_code, place_of_supply, is_primary
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id::text, address_type, line1, city, place_of_supply, is_primary
                    """,
                    (
                        aid, org_id, customer_id, address_type, line1, line2, city,
                        state_code, postal_code, country_code, place_of_supply, is_primary,
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})

    def list_by_customer(self, org_id: str, *, customer_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, address_type, line1, line2, city, state_code,
                           postal_code, country_code, place_of_supply, is_primary
                    FROM erp.customer_addresses
                    WHERE org_id = %s::uuid AND customer_id = %s::uuid
                    ORDER BY is_primary DESC, address_type ASC
                    """,
                    (org_id, customer_id),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


customer_address_repository = CustomerAddressRepository()
