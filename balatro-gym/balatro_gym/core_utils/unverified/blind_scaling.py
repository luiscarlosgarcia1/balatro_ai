"""Blind chip scaling shared across environment implementations."""

BLIND_CHIPS = {
    1: {"small": 300, "big": 450, "boss": 600},
    2: {"small": 450, "big": 675, "boss": 900},
    3: {"small": 600, "big": 900, "boss": 1200},
    4: {"small": 900, "big": 1350, "boss": 1800},
    5: {"small": 1350, "big": 2025, "boss": 2700},
    6: {"small": 2100, "big": 3150, "boss": 4200},
    7: {"small": 3300, "big": 4950, "boss": 6600},
    8: {"small": 5250, "big": 7875, "boss": 10500},
}


def get_blind_chips(ante: int, blind_type: str) -> int:
    """Return the chip requirement for a blind at a given ante."""
    if ante <= 8:
        return BLIND_CHIPS[ante][blind_type]

    base = BLIND_CHIPS[8][blind_type]
    multiplier = 1.5 ** (ante - 8)
    return int(base * multiplier)
