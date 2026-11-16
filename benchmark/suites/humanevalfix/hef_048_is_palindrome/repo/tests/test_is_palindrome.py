"""Unit tests from HumanEvalFix (Python/48), bigcode/humanevalpack, MIT license."""

from is_palindrome import *  # noqa: F403
from is_palindrome import is_palindrome


def check(is_palindrome):
    assert is_palindrome('') == True
    assert is_palindrome('aba') == True
    assert is_palindrome('aaaaa') == True
    assert is_palindrome('zbcd') == False
    assert is_palindrome('xywyx') == True
    assert is_palindrome('xywyz') == False
    assert is_palindrome('xywzx') == False


def test_is_palindrome():
    check(is_palindrome)
