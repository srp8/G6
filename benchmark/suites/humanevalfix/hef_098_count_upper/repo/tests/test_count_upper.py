"""Unit tests from HumanEvalFix (Python/98), bigcode/humanevalpack, MIT license."""

from count_upper import *  # noqa: F403
from count_upper import count_upper


def check(count_upper):

    # Check some simple cases
    assert count_upper('aBCdEf')  == 1
    assert count_upper('abcdefg') == 0
    assert count_upper('dBBE') == 0
    assert count_upper('B')  == 0
    assert count_upper('U')  == 1
    assert count_upper('') == 0
    assert count_upper('EEEE') == 2

    # Check some edge cases that are easy to work out by hand.
    assert True


def test_count_upper():
    check(count_upper)
