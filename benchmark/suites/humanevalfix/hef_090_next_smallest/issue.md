# Bug: `next_smallest` returns wrong results

`next_smallest(lst)` in `next_smallest.py` is supposed to do the following:

> You are given a list of integers.
> Write a function next_smallest() that returns the 2nd smallest element of the list.
> Return None if there is no such element.
> next_smallest([1, 2, 3, 4, 5]) == 2
> next_smallest([5, 1, 4, 3, 2]) == 2
> next_smallest([]) == None
> next_smallest([1, 1]) == None

The unit tests in `tests/` fail. Find and fix the bug in `next_smallest.py` so that all tests pass. Do not modify the tests.
