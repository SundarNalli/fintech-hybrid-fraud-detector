"""One place that decides whether `field <op> expected` is true.

Shared by the verifier (claims) and the hard-fact list, so both agree.
"""

from __future__ import annotations

from hybrid_fraud.core.schemas import Scalar

_MISSING = object()


def holds(fields: dict[str, Scalar], field: str, op: str, expected: Scalar) -> bool:
    """A missing field, or a comparison that makes no sense, is simply false."""
    actual = fields.get(field, _MISSING)
    if actual is _MISSING:
        return False
    try:
        match op:
            case "eq":
                return actual == expected
            case "ne":
                return actual != expected
            case "gt":
                return actual > expected  # type: ignore[operator]
            case "gte":
                return actual >= expected  # type: ignore[operator]
            case "lt":
                return actual < expected  # type: ignore[operator]
            case "lte":
                return actual <= expected  # type: ignore[operator]
            case "contains":
                return isinstance(actual, str) and isinstance(expected, str) and expected in actual
    except TypeError:  # e.g. None > 3: not true, and not a crash
        return False
    return False
