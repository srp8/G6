# Bug: `filter_integers` returns wrong results

`filter_integers(values: List[Any]) -> List[int]` in `filter_integers.py` is supposed to do the following:

> Filter given list of any python values only for integers
> >>> filter_integers(['a', 3.14, 5])
> [5]
> >>> filter_integers([1, 2, 3, 'abc', {}, []])
> [1, 2, 3]

The unit tests in `tests/` fail. Find and fix the bug in `filter_integers.py` so that all tests pass. Do not modify the tests.
