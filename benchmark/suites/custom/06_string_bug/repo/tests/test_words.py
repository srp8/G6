from words import reverse_words


def test_three_words():
    assert reverse_words("the quick fox") == "fox quick the"


def test_single_word():
    assert reverse_words("hello") == "hello"


def test_two_words():
    assert reverse_words("good morning") == "morning good"
