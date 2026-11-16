# Bug: `triples_sum_to_zero` returns wrong results

`triples_sum_to_zero(l: list)` in `triples_sum_to_zero.py` is supposed to do the following:

> triples_sum_to_zero takes a list of integers as an input.
> it returns True if there are three distinct elements in the list that
> sum to zero, and False otherwise.
> >>> triples_sum_to_zero([1, 3, 5, 0])
> False
> >>> triples_sum_to_zero([1, 3, -2, 1])
> True
> >>> triples_sum_to_zero([1, 2, 3, 7])
> False
> >>> triples_sum_to_zero([2, 4, -5, 3, 9, 7])
> True
> >>> triples_sum_to_zero([1])
> False

The unit tests in `tests/` fail. Find and fix the bug in `triples_sum_to_zero.py` so that all tests pass. Do not modify the tests.
