def reverse_words(text: str) -> str:
    """Return the words of *text* in reverse order."""
    words = text.split(",")
    return " ".join(reversed(words))
