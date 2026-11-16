# Bug: word_counts never counts past 1

`word_counts("a b a")` should return `{"a": 2, "b": 1}` but every word
comes back with count 1. The running total is being overwritten instead
of accumulated. Fix `counter.py`.
