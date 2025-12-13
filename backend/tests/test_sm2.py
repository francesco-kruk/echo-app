"""Unit tests for SM-2 state update."""

import pytest

from app.srs.sm2 import SM2State, apply_sm2


def test_ef_clamped_to_minimum():
    state = SM2State(ease_factor=1.3, repetitions=0, interval_days=0)
    # Very low quality would decrease EF, but it must remain >= 1.3
    new_state = apply_sm2(state, quality=0)
    assert new_state.ease_factor >= 1.3


def test_lapse_resets_repetitions_and_sets_interval_1():
    state = SM2State(ease_factor=2.5, repetitions=5, interval_days=30)
    new_state = apply_sm2(state, quality=0)
    assert new_state.repetitions == 0
    assert new_state.interval_days == 1


def test_success_increments_repetitions_and_interval_rules():
    # First success
    state = SM2State(ease_factor=2.5, repetitions=0, interval_days=0)
    s1 = apply_sm2(state, quality=4)
    assert s1.repetitions == 1
    assert s1.interval_days == 1

    # Second success
    s2 = apply_sm2(s1, quality=4)
    assert s2.repetitions == 2
    assert s2.interval_days == 6

    # Third success uses prior interval * EF'
    s3 = apply_sm2(s2, quality=4)
    assert s3.repetitions == 3
    assert s3.interval_days >= 1


def test_quality_out_of_range_raises():
    state = SM2State(ease_factor=2.5, repetitions=0, interval_days=0)
    with pytest.raises(ValueError):
        apply_sm2(state, quality=-1)
    with pytest.raises(ValueError):
        apply_sm2(state, quality=6)
