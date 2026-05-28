import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("WORKFLOW_PG_INTEGRATION", "").lower() not in {"1", "true", "yes"},
    reason="Set WORKFLOW_PG_INTEGRATION=1 with migrated PostgreSQL to run DB integration tests",
)


@pytest.mark.integration
def test_schema_tables_exist_when_enabled() -> None:
    from app.modules.workflows.services.workflow_service import workflow_service

    assert workflow_service.schema_ready() is True


@pytest.mark.integration
def test_start_and_list_instance_when_enabled() -> None:
    from app.modules.workflows.repositories import workflow_repo
    from app.modules.workflows.services.workflow_service import workflow_service

    org_id = os.getenv("WORKFLOW_TEST_ORG_ID", "11111111-1111-4111-8111-111111111111")
    if not workflow_service.schema_ready():
        pytest.skip("workflow schema not ready")
    inst = workflow_service.start_workflow(
        org_id=org_id,
        workflow_key="AP_INVOICE_APPROVAL",
        entity_type="invoice",
        entity_id="int-test-inv",
        metadata={"amount": 1200},
    )
    assert inst.get("id")
    fetched = workflow_repo.get_instance(org_id, inst["id"])
    assert fetched is not None
    assert fetched["workflow_type"] == "AP_INVOICE_APPROVAL"
