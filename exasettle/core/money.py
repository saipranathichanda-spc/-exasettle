"""
Monetary calculation utilities for ExaSettle.
Enforces integer paise precision to prevent IEEE-754 floating-point inaccuracies.
1 INR = 100 paise.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def rupees_to_paise(amount_rupees: Union[float, int, str, Decimal]) -> int:
    """Convert INR rupees to integer paise deterministically."""
    if isinstance(amount_rupees, int):
        return amount_rupees * 100
    dec = Decimal(str(amount_rupees))
    paise_dec = (dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(paise_dec)


def paise_to_rupees(amount_paise: int) -> Decimal:
    """Convert integer paise to Decimal rupees."""
    if not isinstance(amount_paise, int):
        raise TypeError(f"amount_paise must be int, got {type(amount_paise)}")
    return Decimal(amount_paise) / Decimal("100")


def format_inr(amount_paise: int, include_symbol: bool = True) -> str:
    """Format integer paise into Indian numbering format (e.g. ₹ 1,23,456.78)."""
    sign = "-" if amount_paise < 0 else ""
    abs_paise = abs(amount_paise)
    rupees_part = abs_paise // 100
    paise_part = abs_paise % 100

    s = str(rupees_part)
    if len(s) <= 3:
        formatted_rupees = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        groups.append(last3)
        formatted_rupees = ",".join(groups)

    formatted_number = f"{formatted_rupees}.{paise_part:02d}"
    if include_symbol:
        return f"-₹{formatted_number}" if sign else f"₹{formatted_number}"
    return f"-{formatted_number}" if sign else formatted_number
