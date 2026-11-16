# Bug: `largest_smallest_integers` returns wrong results

`largest_smallest_integers(lst)` in `largest_smallest_integers.py` is supposed to do the following:

> Create a function that returns a tuple (a, b), where 'a' is
> the largest of negative integers, and 'b' is the smallest
> of positive integers in a list.
> If there is no negative or positive integers, return them as None.
> Examples:
> largest_smallest_integers([2, 4, 1, 3, 5, 7]) == (None, 1)
> largest_smallest_integers([]) == (None, None)
> largest_smallest_integers([0]) == (None, None)

The unit tests in `tests/` fail. Find and fix the bug in `largest_smallest_integers.py` so that all tests pass. Do not modify the tests.
