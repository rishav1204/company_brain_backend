from datetime import datetime, timedelta, timezone


def classify_memory_retention(memory_type: str, created_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    age = now - created_at
    if memory_type == "short_term" and age > timedelta(days=7):
        return "expire"
    if memory_type in {"long_term", "workflow"} and age > timedelta(days=730):
        return "archive"
    if memory_type == "decision":
        return "retain"
    if age > timedelta(days=30):
        return "review"
    return "retain"


if __name__ == "__main__":
    sample = classify_memory_retention("short_term", datetime.now(timezone.utc) - timedelta(days=9))
    print({"result": sample})
