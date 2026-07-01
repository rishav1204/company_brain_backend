#!/usr/bin/env python3
"""Extract Pydantic model fields for frontend module reference generation."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api" / "app"
MODULES = API_ROOT / "modules"
LEGACY_ROUTES = API_ROOT / "api" / "routes"


def type_str(node: ast.expr | None) -> str:
    if node is None:
        return "any"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Subscript):
        base = type_str(node.value)
        if isinstance(node.slice, ast.Tuple):
            args = ", ".join(type_str(elt) for elt in node.slice.elts)
        else:
            args = type_str(node.slice)
        return f"{base}[{args}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return f"{type_str(node.left)} | {type_str(node.right)}"
    if isinstance(node, ast.Attribute):
        return f"{type_str(node.value)}.{node.attr}"
    return ast.unparse(node) if hasattr(ast, "unparse") else "any"


def parse_pydantic_models(path: Path) -> dict[str, list[dict]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    models: dict[str, list[dict]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {getattr(b, "id", "") for b in node.bases}
        if "BaseModel" not in bases and not any(
            isinstance(b, ast.Attribute) and b.attr == "BaseModel" for b in node.bases
        ):
            continue
        fields: list[dict] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                name = item.target.id
                ftype = type_str(item.annotation)
                required = item.value is None
                default = None
                if item.value is not None:
                    try:
                        default = ast.literal_eval(item.value)
                    except Exception:
                        default = ast.unparse(item.value) if hasattr(ast, "unparse") else "..."
                fields.append(
                    {"name": name, "type": ftype, "required": required, "default": default}
                )
        if fields:
            models[node.name] = fields
    return models


def parse_routes(path: Path) -> list[dict]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    routes: list[dict] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            if not isinstance(dec.func, ast.Attribute):
                continue
            if dec.func.attr not in ("get", "post", "put", "patch", "delete"):
                continue
            path_val = ""
            if dec.args and isinstance(dec.args[0], ast.Constant):
                path_val = dec.args[0].value
            response_model = None
            for kw in dec.keywords:
                if kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                    response_model = kw.value.id
            routes.append(
                {
                    "method": dec.func.attr.upper(),
                    "path": path_val,
                    "func": node.name,
                    "response_model": response_model,
                }
            )
    return routes


def main() -> None:
    out: dict = {"schemas": {}, "routes_by_module": {}}
    for schema_path in sorted(MODULES.rglob("schemas/*.py")):
        if schema_path.name == "__init__.py":
            continue
        rel = str(schema_path.relative_to(MODULES)).replace("\\", "/")
        models = parse_pydantic_models(schema_path)
        if models:
            out["schemas"][rel] = models

    for route_path in sorted(MODULES.rglob("routes/*.py")):
        if route_path.name == "__init__.py":
            continue
        rel = str(route_path.relative_to(MODULES)).replace("\\", "/")
        routes = parse_routes(route_path)
        if routes:
            out["routes_by_module"][rel] = routes

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
