# Bug: `reverse_delete` returns wrong results

`reverse_delete(s,c)` in `reverse_delete.py` is supposed to do the following:

> Task
> We are given two strings s and c, you have to deleted all the characters in s that are equal to any character in c
> then check if the result string is palindrome.
> A string is called palindrome if it reads the same backward as forward.
> You should return a tuple containing the result string and True/False for the check.
> Example
> For s = "abcde", c = "ae", the result should be ('bcd',False)
> For s = "abcdef", c = "b"  the result should be ('acdef',False)
> For s = "abcdedcba", c = "ab", the result should be ('cdedc',True)

The unit tests in `tests/` fail. Find and fix the bug in `reverse_delete.py` so that all tests pass. Do not modify the tests.
