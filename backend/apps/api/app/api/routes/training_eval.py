from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.schemas.training_eval import (
    CanaryAdvanceRequest,
    EvalRunItem,
    EvalRunStartRequest,
    FeedbackEventCreateRequest,
    GovernanceCycleItem,
    GovernanceCycleStartRequest,
    GovernanceRollbackRequest,
    LabelingTaskItem,
    QAGoldExampleCreateRequest,
    QAGoldExampleItem,
    RetrievalJudgmentCreateRequest,
    RetrievalJudgmentItem,
    SafetyEventCreateRequest,
)
from app.services.learning_governance_service import (
    advance_canary,
    approve_labeling_task,
    approve_promotion,
    rollback_cycle,
    run_shadow_eval,
    start_governance_cycle,
    triage_feedback_events,
)
from app.services.repositories import audit_repo, learning_governance_repo, training_eval_repo
from app.services.training_eval_service import run_eval_metrics

router = APIRouter(tags=["training-eval"])


@router.post("/training/qa-gold", response_model=QAGoldExampleItem)
def create_qa_gold(request: QAGoldExampleCreateRequest, context=Depends(build_request_context)) -> QAGoldExampleItem:
    row = training_eval_repo.create_qa_gold_example(
        org_id=context.org_id,
        org_scope=request.org_scope,
        question=request.question,
        expected_answer=request.expected_answer,
        expected_citations=request.expected_citations,
        tags=request.tags,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.qa_gold.created",
        object_ref=f"qa_gold:{row['id']}",
        payload_jsonb={"question": request.question},
    )
    return QAGoldExampleItem(**row)


@router.get("/training/qa-gold")
def list_qa_gold(context=Depends(build_request_context)) -> dict:
    rows = [QAGoldExampleItem(**row) for row in training_eval_repo.list_qa_gold_examples(org_id=context.org_id)]
    return {
        "request_id": context.request_id,
        "items": rows,
        "confidence": 0.95,
        "verification_status": "training_gold_examples_loaded",
    }


@router.post("/training/retrieval-judgments", response_model=RetrievalJudgmentItem)
def create_retrieval_judgment(
    request: RetrievalJudgmentCreateRequest, context=Depends(build_request_context)
) -> RetrievalJudgmentItem:
    row = training_eval_repo.create_retrieval_judgment(
        org_id=context.org_id,
        query=request.query,
        candidate_ref=request.candidate_ref,
        relevance_label=request.relevance_label,
        judged_by=request.judged_by,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.retrieval_judgment.created",
        object_ref=f"retrieval_judgment:{row['id']}",
        payload_jsonb={"query": request.query, "candidate_ref": request.candidate_ref},
    )
    return RetrievalJudgmentItem(**row)


@router.get("/training/retrieval-judgments")
def list_retrieval_judgments(context=Depends(build_request_context)) -> dict:
    rows = [RetrievalJudgmentItem(**row) for row in training_eval_repo.list_retrieval_judgments(org_id=context.org_id)]
    return {
        "request_id": context.request_id,
        "items": rows,
        "confidence": 0.95,
        "verification_status": "retrieval_judgments_loaded",
    }


@router.post("/training/safety-events")
def create_safety_event(request: SafetyEventCreateRequest, context=Depends(build_request_context)) -> dict:
    row = training_eval_repo.create_safety_event(
        org_id=context.org_id,
        event_type=request.event_type,
        severity=request.severity,
        request_id=request.request_id,
        details=request.details,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.safety_event.created",
        object_ref=f"safety_event:{row['id']}",
        payload_jsonb={"event_type": request.event_type, "severity": request.severity},
    )
    return {
        "request_id": context.request_id,
        "id": row["id"],
        "confidence": 0.96,
        "verification_status": "safety_event_recorded",
    }


@router.post("/training/feedback")
def create_feedback_event(request: FeedbackEventCreateRequest, context=Depends(build_request_context)) -> dict:
    row = training_eval_repo.create_feedback_event(
        org_id=context.org_id,
        event_type=request.event_type,
        payload_jsonb=request.payload_jsonb,
        created_by=request.created_by,
    )
    triage_result = triage_feedback_events(org_id=context.org_id)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.feedback.created",
        object_ref=f"feedback_event:{row['id']}",
        payload_jsonb={"event_type": request.event_type, "triage": triage_result},
    )
    return {
        "request_id": context.request_id,
        "id": row["id"],
        "triage": triage_result,
        "confidence": 0.95,
        "verification_status": "feedback_recorded_and_triaged",
    }


@router.post("/training/feedback/triage")
def triage_feedback(context=Depends(build_request_context)) -> dict:
    result = triage_feedback_events(org_id=context.org_id)
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.95,
        "verification_status": "feedback_triage_completed",
    }


@router.get("/training/labeling-tasks")
def list_labeling_tasks(status: str | None = None, context=Depends(build_request_context)) -> dict:
    rows = [
        LabelingTaskItem(**row) for row in learning_governance_repo.list_labeling_tasks(org_id=context.org_id, status=status)
    ]
    return {
        "request_id": context.request_id,
        "items": rows,
        "confidence": 0.95,
        "verification_status": "labeling_tasks_loaded",
    }


@router.post("/training/labeling-tasks/{task_id}/approve")
def approve_labeling(task_id: str, context=Depends(build_request_context)) -> dict:
    row = approve_labeling_task(org_id=context.org_id, task_id=task_id, reviewer_id=context.user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Labeling task not found")
    return {
        "request_id": context.request_id,
        "task": LabelingTaskItem(**row),
        "confidence": 0.97,
        "verification_status": "labeling_task_approved",
    }


@router.post("/training/governance/cycles/start", response_model=GovernanceCycleItem)
def start_cycle(request: GovernanceCycleStartRequest, context=Depends(build_request_context)) -> GovernanceCycleItem:
    row = start_governance_cycle(
        org_id=context.org_id,
        candidate_version=request.candidate_version,
        created_by=context.user_id,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.governance_cycle.started",
        object_ref=f"governance_cycle:{row['id']}",
        payload_jsonb={"candidate_version": request.candidate_version},
    )
    return GovernanceCycleItem(**row)


@router.get("/training/governance/cycles")
def list_cycles(context=Depends(build_request_context)) -> dict:
    rows = [GovernanceCycleItem(**row) for row in learning_governance_repo.list_cycles(org_id=context.org_id)]
    return {
        "request_id": context.request_id,
        "items": rows,
        "confidence": 0.95,
        "verification_status": "governance_cycles_loaded",
    }


@router.post("/training/governance/cycles/{cycle_id}/shadow-eval")
def shadow_eval(cycle_id: str, context=Depends(build_request_context)) -> dict:
    result = run_shadow_eval(org_id=context.org_id, cycle_id=cycle_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail", "shadow_eval_failed"))
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="system",
        actor_id="shadow-eval-runner",
        event_type="training.governance_cycle.shadow_eval",
        object_ref=f"governance_cycle:{cycle_id}",
        payload_jsonb=result.get("comparison", {}),
    )
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.96,
        "verification_status": "shadow_eval_completed",
    }


@router.post("/training/governance/cycles/{cycle_id}/approve-promotion")
def approve_cycle_promotion(cycle_id: str, context=Depends(build_request_context)) -> dict:
    result = approve_promotion(
        org_id=context.org_id,
        cycle_id=cycle_id,
        approver_id=context.user_id,
        roles=context.roles,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=403, detail=result.get("detail", "promotion_denied"))
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.governance_cycle.approved",
        object_ref=f"governance_cycle:{cycle_id}",
        payload_jsonb={"approver_id": context.user_id},
    )
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.98,
        "verification_status": "governance_promotion_approved",
    }


@router.post("/training/governance/cycles/{cycle_id}/canary")
def advance_cycle_canary(
    cycle_id: str, request: CanaryAdvanceRequest, context=Depends(build_request_context)
) -> dict:
    result = advance_canary(org_id=context.org_id, cycle_id=cycle_id, canary_percent=request.canary_percent)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail", "canary_advance_failed"))
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.96,
        "verification_status": "canary_advanced",
    }


@router.post("/training/governance/cycles/{cycle_id}/rollback")
def rollback_governance_cycle(
    cycle_id: str, request: GovernanceRollbackRequest, context=Depends(build_request_context)
) -> dict:
    result = rollback_cycle(org_id=context.org_id, cycle_id=cycle_id, reason=request.reason)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("detail", "cycle_not_found"))
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="training.governance_cycle.rolled_back",
        object_ref=f"governance_cycle:{cycle_id}",
        payload_jsonb={"reason": request.reason},
    )
    return {
        "request_id": context.request_id,
        "result": result,
        "confidence": 0.97,
        "verification_status": "governance_cycle_rolled_back",
    }


@router.post("/training/eval-runs/start", response_model=EvalRunItem)
def start_eval_run(request: EvalRunStartRequest, context=Depends(build_request_context)) -> EvalRunItem:
    row = training_eval_repo.start_eval_run(org_id=context.org_id, run_type=request.run_type)
    return EvalRunItem(**row)


@router.post("/training/eval-runs/{run_id}/complete", response_model=EvalRunItem)
def complete_eval_run(run_id: str, context=Depends(build_request_context)) -> EvalRunItem:
    metrics = run_eval_metrics(org_id=context.org_id)
    row = training_eval_repo.complete_eval_run(org_id=context.org_id, run_id=run_id, metrics_jsonb=metrics)
    if row is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="system",
        actor_id="eval-runner",
        event_type="training.eval_run.completed",
        object_ref=f"eval_run:{run_id}",
        payload_jsonb=metrics,
    )
    return EvalRunItem(**row)
