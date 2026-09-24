from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import build_request_context
from app.modules.finance_os.invoice_ai.pipelines.invoice_pipeline import invoice_pipeline
from app.modules.finance_os.invoice_ai.schemas.invoice_ai_schema import (
    AnomalyItem,
    AnomalyListResponse,
    ConfirmDuplicateRequest,
    CopilotRequest,
    CopilotResponse,
    DuplicateScoreResponse,
    ExtractRequest,
    ExtractResponse,
    OverridePredictionRequest,
    PredictRequest,
    PredictResponse,
    PredictionItem,
)
from app.modules.finance_os.invoice_ai.security.invoice_ai_guard import require_invoice_ai_read, require_invoice_ai_write
from app.modules.finance_os.invoice_ai.services.anomaly_service import anomaly_service
from app.modules.finance_os.invoice_ai.services.copilot_service import copilot_service
from app.modules.finance_os.invoice_ai.services.duplicate_service import duplicate_service
from app.modules.finance_os.invoice_ai.services.extraction_service import extraction_service
from app.modules.finance_os.invoice_ai.services.prediction_service import prediction_service

router = APIRouter(prefix="/finance-os/invoice-ai", tags=["finance-os-invoice-ai"])


@router.post("/extract", response_model=ExtractResponse)
def extract_invoice(body: ExtractRequest, context=Depends(build_request_context)) -> ExtractResponse:
    require_invoice_ai_write(context.user)
    org_id = str(context.org_id)
    result = invoice_pipeline.run(org_id, document_id=body.document_id, invoice_type=body.invoice_type)
    row = extraction_service.get(org_id, result["extraction_id"]) or {}
    return ExtractResponse(
        extraction_id=result["extraction_id"],
        document_id=body.document_id,
        invoice_number=row.get("invoice_number"),
        vendor_name=row.get("vendor_name"),
        vendor_gstin=row.get("vendor_gstin"),
        total_amount=float(row.get("total_amount") or 0),
        extraction_confidence=float(row.get("extraction_confidence") or 0),
        confidence_band=result.get("confidence_band", "manual_review"),
    )


@router.post("/predict", response_model=PredictResponse)
def predict_invoice(body: PredictRequest, context=Depends(build_request_context)) -> PredictResponse:
    require_invoice_ai_write(context.user)
    org_id = str(context.org_id)
    try:
        result = prediction_service.predict(org_id, extraction_id=body.extraction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items = [
        PredictionItem(
            id=str(p["id"]),
            prediction_type=str(p["prediction_type"]),
            suggested_account_id=p.get("suggested_account_id"),
            suggested_gst_code=p.get("suggested_gst_code"),
            confidence_score=float(p.get("confidence_score") or 0),
            metadata=p.get("metadata") or {},
        )
        for p in result.get("predictions", [])
    ]
    return PredictResponse(
        extraction_id=body.extraction_id,
        predictions=items,
        overall_confidence=float(result.get("overall_confidence") or 0),
        confidence_band=str(result.get("confidence_band") or "manual_review"),
    )


@router.get("/suggestions")
def list_suggestions(
    context=Depends(build_request_context),
    extraction_id: str = Query(...),
) -> dict:
    require_invoice_ai_read(context.user)
    org_id = str(context.org_id)
    items = prediction_service.list_suggestions(org_id, extraction_id=extraction_id)
    return {"extraction_id": extraction_id, "predictions": items}


@router.get("/duplicates", response_model=DuplicateScoreResponse)
def get_duplicates(
    context=Depends(build_request_context),
    extraction_id: str = Query(...),
) -> DuplicateScoreResponse:
    require_invoice_ai_read(context.user)
    org_id = str(context.org_id)
    row = duplicate_service.latest(org_id, extraction_id)
    if not row:
        return DuplicateScoreResponse(extraction_id=extraction_id, status="clean")
    return DuplicateScoreResponse(
        extraction_id=extraction_id,
        status=str(row.get("status") or "clean"),
        similarity_score=float(row.get("similarity_score") or 0),
        matched_invoice_id=row.get("matched_invoice_id"),
        score_breakdown=row.get("score_breakdown") or {},
    )


@router.get("/review-queue")
def review_queue(
    context=Depends(build_request_context),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    require_invoice_ai_read(context.user)
    items = extraction_service.list_review_queue(str(context.org_id), limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/anomalies", response_model=AnomalyListResponse)
def list_anomalies(
    context=Depends(build_request_context),
    extraction_id: str | None = Query(default=None),
) -> AnomalyListResponse:
    require_invoice_ai_read(context.user)
    org_id = str(context.org_id)
    if extraction_id:
        rows = anomaly_service.list_for_extraction(org_id, extraction_id)
    else:
        rows = anomaly_service.list_recent(org_id)
    return AnomalyListResponse(
        extraction_id=extraction_id,
        anomalies=[
            AnomalyItem(
                id=str(r["id"]),
                anomaly_type=str(r["anomaly_type"]),
                anomaly_score=float(r.get("anomaly_score") or 0),
                severity=str(r.get("severity") or "medium"),
                description=str(r.get("description") or ""),
                status=str(r.get("status") or "open"),
            )
            for r in rows
        ],
    )


@router.get("/extractions/{extraction_id}")
def get_extraction(extraction_id: str, context=Depends(build_request_context)) -> dict:
    require_invoice_ai_read(context.user)
    org_id = str(context.org_id)
    row = extraction_service.get(org_id, extraction_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return row


@router.post("/copilot", response_model=CopilotResponse)
def copilot(body: CopilotRequest, context=Depends(build_request_context)) -> CopilotResponse:
    require_invoice_ai_read(context.user)
    org_id = str(context.org_id)
    answer = copilot_service.answer(org_id, extraction_id=body.extraction_id, question=body.question)
    return CopilotResponse(answer=answer, extraction_id=body.extraction_id)


@router.post("/confirm-duplicate")
def confirm_duplicate(body: ConfirmDuplicateRequest, context=Depends(build_request_context)) -> dict:
    require_invoice_ai_write(context.user)
    org_id = str(context.org_id)
    row = duplicate_service.confirm(
        org_id,
        extraction_id=body.extraction_id,
        status=body.status,
        matched_invoice_id=body.matched_invoice_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Duplicate score not found")
    return row


@router.post("/override-prediction")
def override_prediction(body: OverridePredictionRequest, context=Depends(build_request_context)) -> dict:
    require_invoice_ai_write(context.user)
    org_id = str(context.org_id)
    row = prediction_service.override_prediction(
        org_id,
        prediction_id=body.prediction_id,
        suggested_account_id=body.suggested_account_id,
        suggested_gst_code=body.suggested_gst_code,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return row
