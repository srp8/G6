"""Unit tests from HumanEvalFix (Python/42), bigcode/humanevalpack, MIT license."""

from incr_list import *  # noqa: F403
from incr_list import incr_list


def check(incr_list):
    assert incr_list([]) == []
    assert incr_list([3, 2, 1]) == [4, 3, 2]
    assert incr_list([5, 2, 5, 2, 3, 3, 9, 0, 123]) == [6, 3, 6, 3, 4, 4, 10, 1, 124]


def test_incr_list():
    check(incr_list)
