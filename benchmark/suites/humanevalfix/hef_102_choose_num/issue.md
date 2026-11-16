# Bug: `choose_num` returns wrong results

`choose_num(x, y)` in `choose_num.py` is supposed to do the following:

> This function takes two positive numbers x and y and returns the
> biggest even integer number that is in the range [x, y] inclusive. If
> there's no such number, then the function should return -1.
> For example:
> choose_num(12, 15) = 14
> choose_num(13, 12) = -1

The unit tests in `tests/` fail. Find and fix the bug in `choose_num.py` so that all tests pass. Do not modify the tests.
