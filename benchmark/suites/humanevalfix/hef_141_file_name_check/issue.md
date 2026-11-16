# Bug: `file_name_check` returns wrong results

`file_name_check(file_name)` in `file_name_check.py` is supposed to do the following:

> Create a function which takes a string representing a file's name, and returns
> 'Yes' if the the file's name is valid, and returns 'No' otherwise.
> A file's name is considered to be valid if and only if all the following conditions
> are met:
> - There should not be more than three digits ('0'-'9') in the file's name.
> - The file's name contains exactly one dot '.'
> - The substring before the dot should not be empty, and it starts with a letter from
> the latin alphapet ('a'-'z' and 'A'-'Z').
> - The substring after the dot should be one of these: ['txt', 'exe', 'dll']
> Examples:
> file_name_check("example.txt") # => 'Yes'
> file_name_check("1example.dll") # => 'No' (the name should start with a latin alphapet letter)

The unit tests in `tests/` fail. Find and fix the bug in `file_name_check.py` so that all tests pass. Do not modify the tests.
