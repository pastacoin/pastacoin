"""Amounts are integers.

Every amount on the chain, in the signed payload and in the REST API is a whole number of
**base units**; one PASTA is ``UNITS_PER_PASTA`` of them. Floats never touch a balance.
Front-ends convert at the edge with :func:`to_units` and :func:`format_units`.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

UNITS_PER_PASTA = 100_000_000
DECIMALS = 8


def as_units(value) -> int:
    """Strictly read an amount that is already in base units. Raises ``ValueError``."""
    if isinstance(value, bool):
        raise ValueError("amount must be a whole number of base units")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError("amount must be a whole number of base units")


def to_units(pasta) -> int:
    """Convert a PASTA amount typed by a person (``"1.5"``, ``2``) to base units, exactly."""
    try:
        d = Decimal(str(pasta).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"not a number: {pasta!r}") from None
    if not d.is_finite():
        raise ValueError(f"not a number: {pasta!r}")
    units = d * UNITS_PER_PASTA
    if units != units.to_integral_value():
        raise ValueError(f"at most {DECIMALS} decimal places")
    return int(units)


def format_units(units: int, places: int | None = None) -> str:
    """Render base units as PASTA: ``150000000 -> "1.5"``. ``places`` fixes the decimals for tables."""
    d = Decimal(int(units)) / UNITS_PER_PASTA
    if places is not None:
        return f"{d:.{places}f}"
    text = f"{d:.{DECIMALS}f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"
