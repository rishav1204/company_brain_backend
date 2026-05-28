from app.services.rate_limiter import FixedWindowRateLimiter

# Stricter limit for authentication endpoints (per email+ip key).
login_rate_limiter = FixedWindowRateLimiter(limit_per_minute=20)
