"""Unit tests from HumanEvalFix (Python/61), bigcode/humanevalpack, MIT license."""

from correct_bracketing import *  # noqa: F403
from correct_bracketing import correct_bracketing


def check(correct_bracketing):
    assert correct_bracketing("()")
    assert correct_bracketing("(()())")
    assert correct_bracketing("()()(()())()")
    assert correct_bracketing("()()((()()())())(()()(()))")
    assert not correct_bracketing("((()())))")
    assert not correct_bracketing(")(()")
    assert not correct_bracketing("(")
    assert not correct_bracketing("((((")
    assert not correct_bracketing(")")
    assert not correct_bracketing("(()")
    assert not correct_bracketing("()()(()())())(()")
    assert not correct_bracketing("()()(()())()))()")


def test_correct_bracketing():
    check(correct_bracketing)
