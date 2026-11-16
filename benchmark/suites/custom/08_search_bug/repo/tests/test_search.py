from search import binary_search


def test_single_element():
    assert binary_search([5], 5) == 0


def test_last_element():
    assert binary_search([1, 3, 5, 7], 7) == 3


def test_found_in_middle():
    assert binary_search([1, 3, 5, 7, 9], 5) == 2


def test_missing_element():
    assert binary_search([1, 3, 5], 4) == -1


def test_empty_list():
    assert binary_search([], 1) == -1
