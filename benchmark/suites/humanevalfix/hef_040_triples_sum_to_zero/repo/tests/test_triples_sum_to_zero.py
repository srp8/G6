"""Unit tests from HumanEvalFix (Python/40), bigcode/humanevalpack, MIT license."""

from triples_sum_to_zero import *  # noqa: F403
from triples_sum_to_zero import triples_sum_to_zero


def check(triples_sum_to_zero):
    assert triples_sum_to_zero([1, 3, 5, 0]) == False
    assert triples_sum_to_zero([1, 3, 5, -1]) == False
    assert triples_sum_to_zero([1, 3, -2, 1]) == True
    assert triples_sum_to_zero([1, 2, 3, 7]) == False
    assert triples_sum_to_zero([1, 2, 5, 7]) == False
    assert triples_sum_to_zero([2, 4, -5, 3, 9, 7]) == True
    assert triples_sum_to_zero([1]) == False
    assert triples_sum_to_zero([1, 3, 5, -100]) == False
    assert triples_sum_to_zero([100, 3, 5, -100]) == False


def test_triples_sum_to_zero():
    check(triples_sum_to_zero)
