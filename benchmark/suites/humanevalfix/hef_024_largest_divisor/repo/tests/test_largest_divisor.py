"""Unit tests from HumanEvalFix (Python/24), bigcode/humanevalpack, MIT license."""

from largest_divisor import *  # noqa: F403
from largest_divisor import largest_divisor


def check(largest_divisor):
    assert largest_divisor(3) == 1
    assert largest_divisor(7) == 1
    assert largest_divisor(10) == 5
    assert largest_divisor(100) == 50
    assert largest_divisor(49) == 7


def test_largest_divisor():
    check(largest_divisor)
