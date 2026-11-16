# Bug: `is_happy` returns wrong results

`is_happy(s)` in `is_happy.py` is supposed to do the following:

> You are given a string s.
> Your task is to check if the string is happy or not.
> A string is happy if its length is at least 3 and every 3 consecutive letters are distinct
> For example:
> is_happy(a) => False
> is_happy(aa) => False
> is_happy(abcd) => True
> is_happy(aabb) => False
> is_happy(adb) => True
> is_happy(xyy) => False

The unit tests in `tests/` fail. Find and fix the bug in `is_happy.py` so that all tests pass. Do not modify the tests.
