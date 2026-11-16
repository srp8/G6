from text_utils import slugify, title_case


def test_title_case_still_works():
    assert title_case("hello world") == "Hello World"


def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_collapses_spaces():
    assert slugify("  Multiple   spaces ") == "multiple-spaces"


def test_slugify_numbers_kept():
    assert slugify("Python 3.12 Rocks") == "python-3-12-rocks"
