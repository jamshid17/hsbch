"""How much of an item can be claimed.

An item with a count is a count: eight skewers are eight, and a ninth claim
describes a meal that didn't happen. One unit or less is a dish rather than a
count, and dishes get shared — which the proportional split is built for, so
those stay uncapped.
"""

from decimal import Decimal

import pytest

from app.routers.sessions import _claim_capacity


@pytest.mark.parametrize(
    "quantity,expected",
    [
        ("8", Decimal("8")),
        ("2", Decimal("2")),
        # Weighed goods: 1.5 kg is one and a half of something countable
        # enough to cap, and half a kilo can't be handed to two people twice.
        ("1.5", Decimal("1")),
        ("8.9", Decimal("8")),
    ],
)
def test_a_counted_item_caps_at_its_whole_units(quantity, expected):
    assert _claim_capacity(Decimal(quantity)) == expected


@pytest.mark.parametrize("quantity", ["1", "0.5", "0"])
def test_a_single_dish_is_shareable_without_limit(quantity):
    """Two people ticking one lagmon is the split working as designed, not
    someone claiming more than exists."""
    assert _claim_capacity(Decimal(quantity)) is None


def test_the_cap_never_exceeds_what_was_ordered():
    """The whole point: the units handed out add up to the units bought."""
    assert _claim_capacity(Decimal("8")) == Decimal("8")
    assert _claim_capacity(Decimal("8")) < Decimal("9")
