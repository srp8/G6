# Bug: `find_max` returns wrong results

`find_max(words)` in `find_max.py` is supposed to do the following:

> Write a function that accepts a list of strings.
> The list contains different words. Return the word with maximum number
> of unique characters. If multiple strings have maximum number of unique
> characters, return the one which comes first in lexicographical order.
> find_max(["name", "of", "string"]) == "string"
> find_max(["name", "enam", "game"]) == "enam"
> find_max(["aaaaaaa", "bb" ,"cc"]) == ""aaaaaaa"

The unit tests in `tests/` fail. Find and fix the bug in `find_max.py` so that all tests pass. Do not modify the tests.
