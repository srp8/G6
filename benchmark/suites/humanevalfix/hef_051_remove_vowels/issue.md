# Bug: `remove_vowels` returns wrong results

`remove_vowels(text)` in `remove_vowels.py` is supposed to do the following:

> remove_vowels is a function that takes string and returns string without vowels.
> >>> remove_vowels('')
> ''
> >>> remove_vowels("abcdef\nghijklm")
> 'bcdf\nghjklm'
> >>> remove_vowels('abcdef')
> 'bcdf'
> >>> remove_vowels('aaaaa')
> ''
> >>> remove_vowels('aaBAA')
> 'B'
> >>> remove_vowels('zbcd')
> 'zbcd'

The unit tests in `tests/` fail. Find and fix the bug in `remove_vowels.py` so that all tests pass. Do not modify the tests.
