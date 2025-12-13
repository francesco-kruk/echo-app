"""SM-2 state update logic.

Note: Scheduling (dueAt) is *not* derived from SM-2 intervals in this app.
We still maintain SM-2 state (EF/repetitions/intervalDays) for coherence and future evolution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SM2State:
    ease_factor: float
    repetitions: int
    interval_days: int


def _clamp_ease_factor(ef: float) -> float:
    return max(1.3, ef)


def apply_sm2(state: SM2State, quality: int) -> SM2State:
    """Apply SM-2 update to the given state.

    quality: 0-5

    Rules:
    - EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02)), clamped to >= 1.3
    - if q < 3: repetitions = 0, intervalDays = 1
    - else:
        repetitions += 1
        if repetitions == 1: intervalDays = 1
        if repetitions == 2: intervalDays = 6
        else: intervalDays = round(previousIntervalDays * EF')
    """
    if quality < 0 or quality > 5:
        raise ValueError("quality must be between 0 and 5")

    ef = state.ease_factor
    reps = state.repetitions
    interval = state.interval_days

    ef_prime = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef_prime = _clamp_ease_factor(ef_prime)

    if quality < 3:
        return SM2State(ease_factor=ef_prime, repetitions=0, interval_days=1)

    reps_prime = reps + 1
    if reps_prime == 1:
        interval_prime = 1
    elif reps_prime == 2:
        interval_prime = 6
    else:
        interval_prime = max(1, round(interval * ef_prime))

    return SM2State(ease_factor=ef_prime, repetitions=reps_prime, interval_days=interval_prime)
