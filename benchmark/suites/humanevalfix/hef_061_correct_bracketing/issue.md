# Bug: `correct_bracketing` returns wrong results

`correct_bracketing(brackets: str)` in `correct_bracketing.py` is supposed to do the following:

> brackets is a string of "(" and ")".
> return True if every opening bracket has a corresponding closing bracket.
> >>> correct_bracketing("(")
> False
> >>> correct_bracketing("()")
> True
> >>> correct_bracketing("(()())")
> True
> >>> correct_bracketing(")(()")
> False

The unit tests in `tests/` fail. Find and fix the bug in `correct_bracketing.py` so that all tests pass. Do not modify the tests.
