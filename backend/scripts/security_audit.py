import json
import subprocess
import sys


def run() -> int:
    command = [sys.executable, "-m", "pip", "list", "--format=json"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=True))
        return 1
    packages = json.loads(result.stdout or "[]")
    audit_cmd = [sys.executable, "-m", "pip", "audit", "--format=json"]
    vulns = []
    try:
        audit_result = subprocess.run(audit_cmd, check=False, capture_output=True, text=True)
        if audit_result.stdout.strip():
            parsed = json.loads(audit_result.stdout)
            if isinstance(parsed, list):
                vulns = parsed
            elif isinstance(parsed, dict):
                vulns = parsed.get("dependencies", [])
    except Exception:
        vulns = []
    high_or_critical = []
    for item in vulns:
        vulnerability_entries = item.get("vulns", []) if isinstance(item, dict) else []
        for vuln in vulnerability_entries:
            severity = str(vuln.get("severity", "")).lower()
            if severity in {"high", "critical"}:
                high_or_critical.append(vuln)
    summary = {
        "status": "ok" if not high_or_critical else "failed",
        "package_count": len(packages),
        "high_or_critical_vulnerabilities": len(high_or_critical),
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0 if not high_or_critical else 1


if __name__ == "__main__":
    raise SystemExit(run())
