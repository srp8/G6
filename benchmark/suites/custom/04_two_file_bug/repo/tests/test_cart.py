from cart import Item, order_total


def test_large_order_ships_free():
    assert order_total([Item(price=30.0, quantity=2)]) == 60.0


def test_small_order_pays_shipping():
    assert order_total([Item(price=10.0, quantity=3)]) == 37.5


def test_threshold_is_fifty():
    assert order_total([Item(price=50.0, quantity=1)]) == 50.0


def test_just_under_threshold():
    assert order_total([Item(price=49.0, quantity=1)]) == 56.5
