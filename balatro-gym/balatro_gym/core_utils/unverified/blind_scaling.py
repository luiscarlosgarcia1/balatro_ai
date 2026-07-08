"""Blind chip scaling shared across environment implementations.

Matches Balatro's ``get_blind_amount(ante) * blind.mult * ante_scaling``.
"""

import math

BASE_BLIND_AMOUNTS = {
    1: 300,
    2: 800,
    3: 2000,
    4: 5000,
    5: 11000,
    6: 20000,
    7: 35000,
    8: 50000,
}

BLIND_MULTIPLIERS = {
    "small": 1,
    "big": 1.5,
    "boss": 2,
}

BLIND_CHIPS = {
    ante: {
        blind_type: int(amount * mult)
        for blind_type, mult in BLIND_MULTIPLIERS.items()
    }
    for ante, amount in BASE_BLIND_AMOUNTS.items()
}


def get_blind_amount(ante: int) -> int:
    """Return Balatro's base blind amount for an ante at normal scaling."""
    if ante < 1:
        return 100
    if ante <= 8:
        return BASE_BLIND_AMOUNTS[ante]

    k = 0.75
    a, b, c, d = BASE_BLIND_AMOUNTS[8], 1.6, ante - 8, 1 + 0.2 * (ante - 8)
    amount = math.floor(a * (b + (k * c) ** d) ** c)
    rounding = 10 ** math.floor(math.log10(amount) - 1)
    return int(amount - amount % rounding)


def get_blind_chips(ante: int, blind_type: str, ante_scaling: float = 1) -> int:
    """Return the chip requirement for a blind at a given ante."""
    return int(get_blind_amount(ante) * BLIND_MULTIPLIERS[blind_type] * ante_scaling)
