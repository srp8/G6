# Bug: `smallest_change` returns wrong results

`smallest_change(arr)` in `smallest_change.py` is supposed to do the following:

> Given an array arr of integers, find the minimum number of elements that
> need to be changed to make the array palindromic. A palindromic array is an array that
> is read the same backwards and forwards. In one change, you can change one element to any other element.
> For example:
> smallest_change([1,2,3,5,4,7,9,6]) == 4
> smallest_change([1, 2, 3, 4, 3, 2, 2]) == 1
> smallest_change([1, 2, 3, 2, 1]) == 0

The unit tests in `tests/` fail. Find and fix the bug in `smallest_change.py` so that all tests pass. Do not modify the tests.
