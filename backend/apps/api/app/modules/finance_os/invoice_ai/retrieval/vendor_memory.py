from __future__ import annotations



from app.modules.finance_os.memory.engine.retrieval_engine import search





def retrieve_vendor_patterns(org_id: str, *, vendor_name: str, top_k: int = 5) -> list[dict]:

    hits = search(org_id, f"vendor invoice accounting pattern {vendor_name}", memory_type="vendor", top_k=top_k)

    if hits:

        return [{"content": h.get("content", ""), "score": h.get("final_score", 0), "metadata": h} for h in hits]

    from app.services.retrieval_service import retrieve_context



    contexts, citations = retrieve_context(

        org_id,

        query=f"vendor invoice accounting pattern {vendor_name}",

        metadata_filter={"doc_type": "accounting_pattern"},

        top_k=top_k,

    )

    patterns: list[dict] = []

    for ctx, cite in zip(contexts, citations):

        patterns.append({"content": ctx, "score": cite.confidence, "metadata": {}})

    return patterns





def retrieve_similar_invoices(org_id: str, *, vendor_name: str, invoice_text: str, top_k: int = 5) -> list[dict]:

    query = f"{vendor_name} invoice {invoice_text[:200]}"

    hits = search(org_id, query, memory_type="vendor", top_k=top_k)

    if hits:

        return [{"content": h.get("content", ""), "score": h.get("final_score", 0)} for h in hits]

    from app.services.retrieval_service import retrieve_context



    contexts, citations = retrieve_context(

        org_id,

        query=query,

        metadata_filter={"doc_type": "invoice"},

        top_k=top_k,

    )

    return [

        {"content": ctx, "score": cite.confidence}

        for ctx, cite in zip(contexts, citations)

    ]

