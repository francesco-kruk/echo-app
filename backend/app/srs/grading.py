"""Deterministic grading heuristic for SRS.

This module contains the pure function for computing grades based on
session state (revealed, attempt_count). The model provides resolution
signals, but the actual grade is computed deterministically here.
"""

from __future__ import annotations

from typing import Literal


Grade = Literal["again", "hard", "good", "easy"]


def compute_grade(revealed: bool, attempt_count: int) -> Grade:
    """Compute the SRS grade from session state.

    Rules:
    - If the answer was revealed → "again" (failed recall)
    - If correct on first attempt → "easy"
    - If correct in 2-3 attempts → "good"
    - If correct after more than 3 attempts → "hard"

    Args:
        revealed: True if the user requested/received the answer
        attempt_count: Number of attempts made before resolution

    Returns:
        The computed grade: "again", "hard", "good", or "easy"

    Raises:
        ValueError: If attempt_count is less than 1 (invalid state)
    """
    if attempt_count < 1:
        raise ValueError(f"attempt_count must be >= 1, got {attempt_count}")

    if revealed:
        return "again"

    if attempt_count == 1:
        return "easy"

    if attempt_count > 3:
        return "hard"

    # attempt_count >= 2 and <= 3
    return "good"
