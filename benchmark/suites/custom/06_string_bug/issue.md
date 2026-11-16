# Bug: reverse_words mangles its input

`reverse_words("the quick fox")` should return `"fox quick the"` but
returns the whole sentence unchanged. Words are separated by whitespace,
not commas. Fix `words.py`.
