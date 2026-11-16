# Bug: `incr_list` returns wrong results

`incr_list(l: list)` in `incr_list.py` is supposed to do the following:

> Return list with elements incremented by 1.
> >>> incr_list([1, 2, 3])
> [2, 3, 4]
> >>> incr_list([5, 3, 5, 2, 3, 3, 9, 0, 123])
> [6, 4, 6, 3, 4, 4, 10, 1, 124]

The unit tests in `tests/` fail. Find and fix the bug in `incr_list.py` so that all tests pass. Do not modify the tests.
