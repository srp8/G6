# Bug: average() crashes on an empty list

Calling `average([])` raises `ZeroDivisionError`. The documented behavior
is that an empty list averages to `0.0`. Add the missing edge case in
`stats.py` without changing the behavior for non-empty lists.
