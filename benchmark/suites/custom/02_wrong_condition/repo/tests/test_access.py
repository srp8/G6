from access import is_adult


def test_exactly_eighteen_is_adult():
    assert is_adult(18) is True


def test_seventeen_is_minor():
    assert is_adult(17) is False


def test_thirty_is_adult():
    assert is_adult(30) is True
