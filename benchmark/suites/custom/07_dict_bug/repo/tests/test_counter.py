from counter import word_counts


def test_repeated_word():
    assert word_counts("a b a") == {"a": 2, "b": 1}


def test_case_insensitive():
    assert word_counts("Hi hi HI") == {"hi": 3}


def test_empty_text():
    assert word_counts("") == {}
