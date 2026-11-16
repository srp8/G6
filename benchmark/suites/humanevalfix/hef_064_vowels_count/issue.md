# Bug: `vowels_count` returns wrong results

`vowels_count(s)` in `vowels_count.py` is supposed to do the following:

> Write a function vowels_count which takes a string representing
> a word as input and returns the number of vowels in the string.
> Vowels in this case are 'a', 'e', 'i', 'o', 'u'. Here, 'y' is also a
> vowel, but only when it is at the end of the given word.
> Example:
> >>> vowels_count("abcde")
> 2
> >>> vowels_count("ACEDY")
> 3

The unit tests in `tests/` fail. Find and fix the bug in `vowels_count.py` so that all tests pass. Do not modify the tests.
