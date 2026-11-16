from mathutils import sum_first_n


def test_sum_of_five():
    assert sum_first_n(5) == 15


def test_sum_of_one():
    assert sum_first_n(1) == 1


def test_sum_of_zero():
    assert sum_first_n(0) == 0
