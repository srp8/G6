# Feature request: add slugify() to text_utils.py

We need a `slugify(text)` function in `text_utils.py` for URL slugs:
lowercase the text, treat every non-alphanumeric character as a word
separator, and join words with single hyphens (no leading/trailing
hyphens). Example: `slugify("Hello, World!")` -> `"hello-world"`.
Tests already exist in `tests/test_text_utils.py`.
