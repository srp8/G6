"""Unit tests from HumanEvalFix (Python/38), bigcode/humanevalpack, MIT license."""

from decode_cyclic import *  # noqa: F403
from decode_cyclic import decode_cyclic


def check(decode_cyclic):
    from random import randint, choice
    import string

    letters = string.ascii_lowercase
    for _ in range(100):
        str = ''.join(choice(letters) for i in range(randint(10, 20)))
        encoded_str = encode_cyclic(str)
        assert decode_cyclic(encoded_str) == str


def test_decode_cyclic():
    check(decode_cyclic)
