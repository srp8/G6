# Bug: order totals are wrong (two problems)

Customers report nonsensical (even negative) order totals, and small
orders are getting free shipping. Our policy: an order's total is the sum
of item price x quantity, plus a $7.50 shipping fee, and orders of $50 or
more ship free. The bug appears to span `cart.py` and `constants.py`.
Make all tests pass.
