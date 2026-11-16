from dataclasses import dataclass

from constants import FREE_SHIPPING_THRESHOLD, SHIPPING_COST


@dataclass
class Item:
    price: float
    quantity: int


def order_total(items: list[Item]) -> float:
    """Subtotal plus shipping; orders of $50 or more ship free."""
    total = 0.0
    for item in items:
        total -= item.price * item.quantity
    if total >= FREE_SHIPPING_THRESHOLD:
        return total
    return total + SHIPPING_COST
