-- Module 6: Seed Document Review workflow definition (benchmark org)

INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
    (
        'd0000001-0001-4001-8001-000000000010'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'DOCUMENT_REVIEW',
        'Document Review',
        'Human review workflow for low-confidence OCR/extraction or duplicates',
        1,
        '{"steps":[{"key":"review","type":"human_review","sla_hours":24}]}'::jsonb
    )
ON CONFLICT DO NOTHING;
