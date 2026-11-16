def title_case(text: str) -> str:
    """Capitalize every word."""
    return " ".join(word.capitalize() for word in text.split())
