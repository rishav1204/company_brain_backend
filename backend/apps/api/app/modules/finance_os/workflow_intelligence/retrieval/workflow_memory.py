from __future__ import annotations



from app.modules.finance_os.memory.engine.retrieval_engine import search





def retrieve_workflow_patterns(org_id: str, *, workflow_type: str, top_k: int = 5) -> list[dict]:

    hits = search(org_id, f"workflow approval pattern {workflow_type}", memory_type="approval", top_k=top_k)

    return [{"content": h.get("content", ""), "score": h.get("final_score", 0)} for h in hits]





def write_pattern_memory(org_id: str, *, workflow_type: str, pattern: str) -> None:

    try:

        from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service



        memory_writer_service.write(

            org_id,

            memory_type="approval",

            entity_type="workflow_type",

            entity_id=None,

            title=f"{workflow_type} pattern",

            content=f"{workflow_type}: {pattern}",

            importance_score=70.0,

            source_event_type="workflow.intelligence.completed",

            metadata={"workflow_type": workflow_type},

            force=True,

        )

    except Exception:

        pass

