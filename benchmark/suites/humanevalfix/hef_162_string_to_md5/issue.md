# Bug: `string_to_md5` returns wrong results

`string_to_md5(text)` in `string_to_md5.py` is supposed to do the following:

> Given a string 'text', return its md5 hash equivalent string.
> If 'text' is an empty string, return None.
> >>> string_to_md5('Hello world') == '3e25960a79dbc69b674cd4ec67a72c62'

The unit tests in `tests/` fail. Find and fix the bug in `string_to_md5.py` so that all tests pass. Do not modify the tests.
