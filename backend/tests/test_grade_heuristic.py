"""Unit tests for the deterministic grading heuristic."""

import pytest

from app.srs.grading import compute_grade


class TestComputeGrade:
    """Tests for compute_grade function."""

    def test_revealed_returns_again(self):
        """When answer is revealed, grade should always be 'again'."""
        # Regardless of attempt count, revealed = again
        assert compute_grade(revealed=True, attempt_count=1) == "again"
        assert compute_grade(revealed=True, attempt_count=2) == "again"
        assert compute_grade(revealed=True, attempt_count=5) == "again"
        assert compute_grade(revealed=True, attempt_count=10) == "again"

    def test_first_attempt_correct_returns_easy(self):
        """When correct on first attempt, grade should be 'easy'."""
        assert compute_grade(revealed=False, attempt_count=1) == "easy"

    def test_two_attempts_returns_good(self):
        """When correct after 2 attempts, grade should be 'good'."""
        assert compute_grade(revealed=False, attempt_count=2) == "good"

    def test_three_attempts_returns_good(self):
        """When correct after 3 attempts, grade should be 'good'."""
        assert compute_grade(revealed=False, attempt_count=3) == "good"

    def test_four_attempts_returns_hard(self):
        """When correct after 4 attempts, grade should be 'hard'."""
        assert compute_grade(revealed=False, attempt_count=4) == "hard"

    def test_many_attempts_returns_hard(self):
        """When correct after many attempts (>3), grade should be 'hard'."""
        assert compute_grade(revealed=False, attempt_count=5) == "hard"
        assert compute_grade(revealed=False, attempt_count=10) == "hard"
        assert compute_grade(revealed=False, attempt_count=100) == "hard"

    def test_invalid_attempt_count_raises_error(self):
        """Invalid attempt_count (<1) should raise ValueError."""
        with pytest.raises(ValueError, match="attempt_count must be >= 1"):
            compute_grade(revealed=False, attempt_count=0)
        
        with pytest.raises(ValueError, match="attempt_count must be >= 1"):
            compute_grade(revealed=False, attempt_count=-1)

    def test_revealed_overrides_attempt_count(self):
        """Revealed flag takes precedence - even if first attempt, revealed = again."""
        # Even on first attempt, if revealed, the grade is 'again'
        assert compute_grade(revealed=True, attempt_count=1) == "again"
        # This is different from correct on first attempt
        assert compute_grade(revealed=False, attempt_count=1) == "easy"

    def test_boundary_conditions(self):
        """Test boundary conditions between grade levels."""
        # Boundary between easy and good (attempt 1 vs 2)
        assert compute_grade(revealed=False, attempt_count=1) == "easy"
        assert compute_grade(revealed=False, attempt_count=2) == "good"
        
        # Boundary between good and hard (attempt 3 vs 4)
        assert compute_grade(revealed=False, attempt_count=3) == "good"
        assert compute_grade(revealed=False, attempt_count=4) == "hard"
