# Bug: binary_search misses elements near the end of the list

`binary_search([5], 5)` returns -1 instead of 0, and searching for the
last element of longer lists also fails intermittently. The loop seems to
stop one step too early. Fix `search.py` without changing the function's
signature or converting it to a linear scan.
