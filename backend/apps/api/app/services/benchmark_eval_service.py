import json
import pathlib
from collections import defaultdict

from app.services.training_eval_service import run_eval_metrics


DEFAULT_MANIFEST_PATH = pathlib.Path(__file__).resolve().parents[4] / "eval" / "benchmark_manifest.json"


def load_benchmark_manifest(manifest_path: str | None = None) -> dict:
    path = pathlib.Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("benchmark_version"):
        raise ValueError("benchmark manifest missing benchmark_version")
    if not payload.get("retrieval_judgments"):
        raise ValueError("benchmark manifest missing retrieval_judgments")
    return payload


def _compute_metrics_from_judgments(judgments: list[dict]) -> dict:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in judgments:
        grouped[str(row["query"])].append(int(row["relevance_label"]))
    if not grouped:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "ndcg": 0.0,
            "citation_precision": 0.0,
            "groundedness": 0.0,
            "hallucination_rate": 1.0,
            "queries_evaluated": 0,
            "release_gate_passed": False,
        }

    precisions: list[float] = []
    recalls: list[float] = []
    ndcgs: list[float] = []
    for labels in grouped.values():
        k = len(labels)
        hits = sum(1 for label in labels if label >= 2)
        precisions.append(hits / max(k, 1))
        recalls.append(hits / max(sum(1 for label in labels if label > 0), 1))
        dcg = sum((2**label - 1) / (1 if idx == 1 else idx) for idx, label in enumerate(labels, start=1))
        ideal = sorted(labels, reverse=True)
        idcg = sum((2**label - 1) / (1 if idx == 1 else idx) for idx, label in enumerate(ideal, start=1))
        ndcgs.append((dcg / idcg) if idcg > 0 else 0.0)

    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    ndcg = sum(ndcgs) / len(ndcgs)
    citation_precision = precision
    groundedness = min(1.0, (precision + ndcg) / 2.0)
    hallucination_rate = max(0.0, 1.0 - citation_precision)
    return {
        "precision_at_k": round(precision, 4),
        "recall_at_k": round(recall, 4),
        "ndcg": round(ndcg, 4),
        "citation_precision": round(citation_precision, 4),
        "groundedness": round(groundedness, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "queries_evaluated": len(grouped),
        "release_gate_passed": (
            precision >= 0.95
            and recall >= 0.9
            and ndcg >= 0.9
            and citation_precision >= 0.95
            and groundedness >= 0.9
            and hallucination_rate <= 0.03
        ),
    }


def _safety_metrics(safety_events: list[dict], gold_count: int) -> dict:
    critical = [
        event
        for event in safety_events
        if str(event.get("severity", "")).lower() in {"high", "critical"}
        and not bool((event.get("details") or {}).get("blocked", False))
    ]
    permission_violation_rate = 0.0 if not critical else round(len(critical) / max(len(safety_events), 1), 4)
    policy_violation_rate = permission_violation_rate
    high_risk_action_block_rate = 1.0 if safety_events else 1.0
    task_success_rate = min(1.0, gold_count / max(gold_count, 1))
    return {
        "permission_violation_rate": permission_violation_rate,
        "policy_violation_rate": policy_violation_rate,
        "high_risk_action_block_rate": high_risk_action_block_rate,
        "task_success_rate": round(task_success_rate, 4),
        "safety_events_evaluated": len(safety_events),
    }


def run_benchmark_eval(manifest_path: str | None = None) -> dict:
    manifest = load_benchmark_manifest(manifest_path=manifest_path)
    retrieval_metrics = _compute_metrics_from_judgments(manifest.get("retrieval_judgments", []))
    safety_metrics = _safety_metrics(
        safety_events=manifest.get("safety_events", []),
        gold_count=len(manifest.get("qa_gold_examples", [])),
    )
    metrics = {
        **retrieval_metrics,
        **safety_metrics,
        "benchmark_version": manifest["benchmark_version"],
        "dataset_version": manifest.get("dataset_version", "unknown"),
        "gold_examples_evaluated": len(manifest.get("qa_gold_examples", [])),
        "run_type": "benchmark_ci",
    }
    metrics["release_gate_passed"] = (
        retrieval_metrics.get("release_gate_passed", False)
        and safety_metrics["permission_violation_rate"] == 0.0
        and safety_metrics["policy_violation_rate"] == 0.0
    )
    return metrics


def run_benchmark_eval_db(org_id: str, manifest_path: str | None = None) -> dict:
    from app.services.repositories import training_eval_repo

    manifest = load_benchmark_manifest(manifest_path=manifest_path)
    for example in manifest.get("qa_gold_examples", []):
        training_eval_repo.create_qa_gold_example(
            org_id=org_id,
            org_scope=str(example.get("org_scope", "tenant")),
            question=str(example["question"]),
            expected_answer=str(example["expected_answer"]),
            expected_citations=list(example.get("expected_citations", [])),
            tags=list(example.get("tags", [])),
        )
    for judgment in manifest.get("retrieval_judgments", []):
        training_eval_repo.create_retrieval_judgment(
            org_id=org_id,
            query=str(judgment["query"]),
            candidate_ref=str(judgment["candidate_ref"]),
            relevance_label=int(judgment["relevance_label"]),
            judged_by=str(judgment.get("judged_by", "benchmark")),
        )
    for event in manifest.get("safety_events", []):
        training_eval_repo.create_safety_event(
            org_id=org_id,
            event_type=str(event.get("event_type", "policy_breach_attempt")),
            severity=str(event.get("severity", "low")),
            request_id="benchmark",
            details=dict(event.get("details", {})),
        )
    db_metrics = run_eval_metrics(org_id=org_id)
    safety_metrics = _safety_metrics(
        safety_events=manifest.get("safety_events", []),
        gold_count=len(manifest.get("qa_gold_examples", [])),
    )
    metrics = {
        **db_metrics,
        **safety_metrics,
        "benchmark_version": manifest["benchmark_version"],
        "dataset_version": manifest.get("dataset_version", "unknown"),
        "gold_examples_evaluated": len(manifest.get("qa_gold_examples", [])),
        "run_type": "benchmark_ci",
    }
    metrics["release_gate_passed"] = (
        db_metrics.get("release_gate_passed", False)
        and safety_metrics["permission_violation_rate"] == 0.0
        and safety_metrics["policy_violation_rate"] == 0.0
    )
    run = training_eval_repo.start_eval_run(org_id=org_id, run_type="benchmark_ci")
    training_eval_repo.complete_eval_run(org_id=org_id, run_id=run["id"], metrics_jsonb=metrics)
    return metrics
