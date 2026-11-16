# Bug: `fib4` returns wrong results

`fib4(n: int)` in `fib4.py` is supposed to do the following:

> The Fib4 number sequence is a sequence similar to the Fibbonacci sequnece that's defined as follows:
> fib4(0) -> 0
> fib4(1) -> 0
> fib4(2) -> 2
> fib4(3) -> 0
> fib4(n) -> fib4(n-1) + fib4(n-2) + fib4(n-3) + fib4(n-4).
> Please write a function to efficiently compute the n-th element of the fib4 number sequence.  Do not use recursion.
> >>> fib4(5)
> 4
> >>> fib4(6)
> 8
> >>> fib4(7)
> 14

The unit tests in `tests/` fail. Find and fix the bug in `fib4.py` so that all tests pass. Do not modify the tests.
