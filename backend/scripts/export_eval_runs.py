import argparse
import json

from app.services.repositories import training_eval_repo


def run(org_id: str, output_path: str) -> int:
    rows = training_eval_repo.list_eval_runs(org_id=org_id)
    payload = {"org_id": org_id, "runs": rows}
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True)
    print(f"Exported {len(rows)} eval runs to {output_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--output-path", required=True)
    args = parser.parse_args()
    raise SystemExit(run(org_id=args.org_id, output_path=args.output_path))
