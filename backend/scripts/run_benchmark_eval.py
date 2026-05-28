import argparse
import json
import os
import sys


def _ensure_api_path() -> None:
    api_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
    if api_root not in sys.path:
        sys.path.insert(0, api_root)


def run_offline(output_path: str, manifest_path: str | None) -> int:
    _ensure_api_path()
    from app.services.benchmark_eval_service import run_benchmark_eval

    metrics = run_benchmark_eval(manifest_path=manifest_path)
    payload = {
        "org_id": "benchmark-offline",
        "runs": [
            {
                "id": "benchmark-offline-run",
                "run_type": metrics.get("run_type", "benchmark_ci"),
                "status": "completed",
                "metrics_jsonb": metrics,
            }
        ],
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True)
    print(f"Benchmark eval completed offline -> {output_path}")
    if not metrics.get("release_gate_passed"):
        print("Benchmark metrics did not pass release gate thresholds.")
        return 1
    return 0


def run_db(org_id: str, output_path: str, manifest_path: str | None) -> int:
    _ensure_api_path()
    from app.services.benchmark_eval_service import load_benchmark_manifest, run_benchmark_eval_db
    from app.services.repositories import training_eval_repo

    manifest = load_benchmark_manifest(manifest_path=manifest_path)
    resolved_org = org_id or str(manifest.get("org_id"))
    metrics = run_benchmark_eval_db(org_id=resolved_org, manifest_path=manifest_path)
    rows = training_eval_repo.list_eval_runs(org_id=resolved_org)
    payload = {"org_id": resolved_org, "runs": rows}
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True)
    print(f"Benchmark eval completed in DB for org={resolved_org} -> {output_path}")
    if not metrics.get("release_gate_passed"):
        print("Benchmark metrics did not pass release gate thresholds.")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--org-id", default="")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--manifest-path", default="")
    args = parser.parse_args()
    manifest_path = args.manifest_path or None
    if args.offline:
        raise SystemExit(run_offline(output_path=args.output_path, manifest_path=manifest_path))
    raise SystemExit(run_db(org_id=args.org_id, output_path=args.output_path, manifest_path=manifest_path))
