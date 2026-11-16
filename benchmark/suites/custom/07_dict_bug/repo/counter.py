def word_counts(text: str) -> dict[str, int]:
    """Count how many times each (lowercased) word appears."""
    counts: dict[str, int] = {}
    for word in text.lower().split():
        counts[word] = 1
    return counts
