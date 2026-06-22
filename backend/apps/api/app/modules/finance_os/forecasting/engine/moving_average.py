from __future__ import annotations


def simple_moving_average(values: list[float], window: int) -> float:
    window = max(1, int(window))
    if not values:
        return 0.0
    slice_ = values[-window:] if len(values) >= window else values
    return float(sum(slice_)) / float(len(slice_))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

