def sum_first_n(n: int) -> int:
    """Return 1 + 2 + ... + n (0 for n <= 0)."""
    total = 0
    for i in range(1, n):
        total += i
    return total
