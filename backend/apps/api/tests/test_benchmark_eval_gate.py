import json
import pathlib
import subprocess
import sys


def test_benchmark_eval_offline_passes_release_gate() -> None:
    from app.services.benchmark_eval_service import run_benchmark_eval

    metrics = run_benchmark_eval()
    assert metrics["run_type"] == "benchmark_ci"
    assert metrics["benchmark_version"]
    assert metrics["queries_evaluated"] >= 3
    assert metrics["release_gate_passed"] is True
    assert metrics["permission_violation_rate"] == 0.0


def test_eval_gate_check_passes_offline_export(tmp_path) -> None:
    from app.services.benchmark_eval_service import run_benchmark_eval

    metrics = run_benchmark_eval()
    export_path = tmp_path / "eval-runs.json"
    export_path.write_text(
        json.dumps({"org_id": "benchmark-offline", "runs": [{"metrics_jsonb": metrics}]}),
        encoding="utf-8",
    )
    gate_script = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "eval_gate_check.py"
    result = subprocess.run(
        [sys.executable, str(gate_script), "--eval-json-path", str(export_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_eval_gate_check_fails_without_benchmark_metadata(tmp_path) -> None:
    export_path = tmp_path / "eval-runs-bad.json"
    export_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "metrics_jsonb": {
                            "precision_at_k": 0.99,
                            "recall_at_k": 0.99,
                            "ndcg": 0.99,
                            "citation_precision": 0.99,
                            "groundedness": 0.99,
                            "hallucination_rate": 0.0,
                            "release_gate_passed": True,
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    gate_script = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "eval_gate_check.py"
    result = subprocess.run(
        [sys.executable, str(gate_script), "--eval-json-path", str(export_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
