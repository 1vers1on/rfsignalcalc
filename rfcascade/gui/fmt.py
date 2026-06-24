"""Small formatting helpers shared across GUI widgets."""

from __future__ import annotations

import math


def num(value: float, digits: int = 2, inf_text: str = "—") -> str:
    """Format a float, showing infinities as a dash (or +inf as '∞')."""
    if value is None:
        return inf_text
    if isinstance(value, float):
        if math.isinf(value):
            return inf_text if value < 0 else "∞"
        if math.isnan(value):
            return inf_text
    return f"{value:.{digits}f}"


def signed(value: float, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return num(value, digits)
    return f"{value:+.{digits}f}"


def parse_float(text: str) -> float:
    """Parse a user-entered float, accepting '', '-', dash and 'inf' forms."""
    text = text.strip().lower()
    if text in ("", "—", "-", "∞", "inf", "+inf"):
        return math.inf
    if text in ("-inf",):
        return -math.inf
    return float(text)
