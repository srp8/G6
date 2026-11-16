"""Unit tests from HumanEvalFix (Python/46), bigcode/humanevalpack, MIT license."""

from fib4 import *  # noqa: F403
from fib4 import fib4


def check(fib4):
    assert fib4(5) == 4
    assert fib4(8) == 28
    assert fib4(10) == 104
    assert fib4(12) == 386


def test_fib4():
    check(fib4)
