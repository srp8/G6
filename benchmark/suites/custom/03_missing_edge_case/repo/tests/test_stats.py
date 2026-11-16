from stats import average


def test_empty_list_is_zero():
    assert average([]) == 0.0


def test_simple_average():
    assert average([2, 4]) == 3.0


def test_single_value():
    assert average([7.5]) == 7.5
