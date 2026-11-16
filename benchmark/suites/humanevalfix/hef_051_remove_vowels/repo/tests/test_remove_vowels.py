"""Unit tests from HumanEvalFix (Python/51), bigcode/humanevalpack, MIT license."""

from remove_vowels import *  # noqa: F403
from remove_vowels import remove_vowels


def check(remove_vowels):
    assert remove_vowels('') == ''
    assert remove_vowels("abcdef\nghijklm") == 'bcdf\nghjklm'
    assert remove_vowels('fedcba') == 'fdcb'
    assert remove_vowels('eeeee') == ''
    assert remove_vowels('acBAA') == 'cB'
    assert remove_vowels('EcBOO') == 'cB'
    assert remove_vowels('ybcd') == 'ybcd'


def test_remove_vowels():
    check(remove_vowels)
