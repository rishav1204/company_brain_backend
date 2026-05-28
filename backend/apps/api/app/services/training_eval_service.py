from collections import defaultdict

from app.services.repositories import training_eval_repo


def _dcg(labels: list[int]) -> float:
    score = 0.0
    for i, rel in enumerate(labels, start=1):
        denom = 1.0 if i == 1 else (i).bit_length()
        score += float((2**rel) - 1) / float(denom)
    return score


def run_eval_metrics(org_id: str) -> dict:
    judgments = training_eval_repo.list_retrieval_judgments(org_id=org_id)
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in judgments:
        grouped[row["query"]].append(int(row["relevance_label"]))

    if not grouped:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "ndcg": 0.0,
            "queries_evaluated": 0,
            "release_gate_passed": False,
        }

    precisions = []
    recalls = []
    ndcgs = []
    for labels in grouped.values():
        k = len(labels)
        hits = sum(1 for x in labels if x >= 2)
        precisions.append(hits / max(k, 1))
        recalls.append(hits / max(sum(1 for x in labels if x > 0), 1))
        dcg = _dcg(labels)
        ideal = sorted(labels, reverse=True)
        idcg = _dcg(ideal)
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
