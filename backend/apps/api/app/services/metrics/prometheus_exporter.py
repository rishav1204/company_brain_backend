from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])
CACHE_HITS = Counter("cache_hit_total", "Read cache hits and misses", ["namespace", "result"])
IAM_LOGIN_SUCCESS = Counter("iam_login_success_total", "IAM login successes")
IAM_LOGIN_FAILURE = Counter("iam_login_failure_total", "IAM login failures")
IAM_REFRESH_REUSE = Counter("iam_refresh_reuse_total", "Refresh token reuse detections")


def record_http_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
    HTTP_LATENCY.labels(method=method, path=path).observe(duration_seconds)


def record_cache_hit(namespace: str, *, hit: bool) -> None:
    CACHE_HITS.labels(namespace=namespace, result="hit" if hit else "miss").inc()


def prometheus_metrics_body() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
