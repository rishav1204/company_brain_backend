from __future__ import annotations


def build_mutation(*, nodes: list[dict] | None = None, edges: list[dict] | None = None) -> dict:
    return {"nodes": nodes or [], "edges": edges or []}


def merge_mutations(*parts: dict | None) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    for part in parts:
        if not part:
            continue
        nodes.extend(part.get("nodes") or [])
        edges.extend(part.get("edges") or [])
    return build_mutation(nodes=nodes, edges=edges)
