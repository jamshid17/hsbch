"""What the split has to get right, in money.

calculator.py is the one place in the app where being wrong costs somebody
cash at the table, and it is pure — no database, no Telegram — so the stubs
below are all the fixture it needs.
"""

import uuid
from decimal import Decimal

import pytest

from app.calculator import calculate_summary, unclaimed_items


class Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def session(tax="0", tip="0"):
    return Stub(tax=Decimal(tax), tip=Decimal(tip))


def item(name, price, quantity="1"):
    return Stub(
        id=uuid.uuid4(), name=name, price=Decimal(price), quantity=Decimal(quantity)
    )


def person(name):
    return Stub(id=uuid.uuid4(), name=name)


def claim(item, person, quantity="1"):
    return Stub(item_id=item.id, person_id=person.id, quantity=Decimal(quantity))


def totals(result):
    """{name: total} — what each person is actually asked to pay."""
    return {r["name"]: r["total"] for r in result}


# ── Splitting an item ────────────────────────────────────────────────────


def test_an_item_one_person_claimed_is_charged_to_them_whole():
    ali, vali = person("Ali"), person("Vali")
    lagmon = item("Lagmon", "50000")

    result = calculate_summary(
        session(), [lagmon], [ali, vali], [claim(lagmon, ali)]
    )

    assert totals(result) == {"Ali": Decimal("50000.00"), "Vali": Decimal("0.00")}


def test_a_shared_item_splits_by_how_much_each_one_claimed():
    ali, vali = person("Ali"), person("Vali")
    # Three portions on the table: Ali took two of them, Vali one.
    plov = item("Palov", "30000", quantity="3")

    result = calculate_summary(
        session(),
        [plov],
        [ali, vali],
        [claim(plov, ali, "2"), claim(plov, vali, "1")],
    )

    assert totals(result) == {"Ali": Decimal("60000.00"), "Vali": Decimal("30000.00")}


def test_the_whole_line_is_distributed_even_when_the_claims_do_not_add_up():
    """Two people claim one portion each of a three-portion dish.

    The dish was paid for in full, so the full line total is shared between
    them — half each — rather than two thirds of it going uncharged.
    """
    ali, vali = person("Ali"), person("Vali")
    plov = item("Palov", "30000", quantity="3")

    result = calculate_summary(
        session(),
        [plov],
        [ali, vali],
        [claim(plov, ali, "1"), claim(plov, vali, "1")],
    )

    assert totals(result) == {"Ali": Decimal("45000.00"), "Vali": Decimal("45000.00")}


# ── Tax and tip ──────────────────────────────────────────────────────────


def test_extras_ride_on_what_each_person_ate():
    """Someone who ate for 90 000 carries three times the service fee of
    someone who ate for 30 000 — not the same flat half."""
    ali, vali = person("Ali"), person("Vali")
    steak, choy = item("Steyk", "90000"), item("Choy", "30000")

    result = calculate_summary(
        session(tip="12000"),
        [steak, choy],
        [ali, vali],
        [claim(steak, ali), claim(choy, vali)],
    )

    assert totals(result) == {
        "Ali": Decimal("99000.00"),
        "Vali": Decimal("33000.00"),
    }


def test_extras_add_up_to_the_exact_amount_despite_rounding():
    """A tip that doesn't divide cleanly still leaves no stray cents.

    Three equal eaters and 10.00 of tip: 3.33 each would lose a cent, so one
    of them carries 3.34 and the three shares add back to exactly 10.00.
    """
    people = [person("A"), person("B"), person("C")]
    dishes = [item(f"Taom {i}", "10.00") for i in range(3)]
    claims = [claim(d, p) for d, p in zip(dishes, people)]

    result = calculate_summary(session(tip="10.00"), dishes, people, claims)

    extras = [r["extras"] for r in result]
    assert sum(extras) == Decimal("10.00")
    assert sorted(extras) == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]


def test_extras_are_split_evenly_when_nobody_claimed_anything():
    """No claims means no weights to go by, and an even split is the only
    sensible reading of "nobody ate anything"."""
    people = [person("A"), person("B")]

    result = calculate_summary(session(tax="5.00", tip="5.00"), [], people, [])

    assert totals(result) == {"A": Decimal("5.00"), "B": Decimal("5.00")}


def test_a_person_who_claimed_nothing_owes_nothing():
    ali, mehmon = person("Ali"), person("Mehmon")
    lagmon = item("Lagmon", "50000")

    result = calculate_summary(
        session(tip="10000"), [lagmon], [ali, mehmon], [claim(lagmon, ali)]
    )

    assert totals(result)["Mehmon"] == Decimal("0.00")


# ── Items nobody claimed ─────────────────────────────────────────────────


def test_an_unclaimed_item_is_named_with_its_line_total():
    non = item("Non", "3000", quantity="3")
    choy = item("Choy", "6000")
    ali = person("Ali")

    left = unclaimed_items([non, choy], [claim(choy, ali)])

    assert left == [{"item_id": non.id, "name": "Non", "amount": Decimal("9000.00")}]


def test_a_zero_quantity_claim_leaves_the_item_unclaimed():
    """Assignments are replaced wholesale rather than deleted one by one, so
    a zero-quantity row is a claim that isn't one."""
    non = item("Non", "3000")
    ali = person("Ali")

    left = unclaimed_items([non], [claim(non, ali, "0")])

    assert [u["name"] for u in left] == ["Non"]


def test_an_unclaimed_item_is_charged_to_nobody():
    """The gap the warning exists for: the people's totals come out below the
    receipt, and only naming the item explains where the rest went."""
    ali = person("Ali")
    lagmon, non = item("Lagmon", "50000"), item("Non", "9000")

    result = calculate_summary(session(), [lagmon, non], [ali], [claim(lagmon, ali)])

    assert sum(r["total"] for r in result) == Decimal("50000.00")
    assert unclaimed_items([lagmon, non], [claim(lagmon, ali)])


def test_nothing_is_unclaimed_once_everything_is_taken():
    ali, vali = person("Ali"), person("Vali")
    lagmon, non = item("Lagmon", "50000"), item("Non", "9000")

    assert (
        unclaimed_items([lagmon, non], [claim(lagmon, ali), claim(non, vali)]) == []
    )


# ── The shape the API relies on ──────────────────────────────────────────


def test_each_person_gets_their_own_items_listed():
    ali, vali = person("Ali"), person("Vali")
    steak, choy = item("Steyk", "90000"), item("Choy", "30000")

    result = calculate_summary(
        session(),
        [steak, choy],
        [ali, vali],
        [claim(steak, ali), claim(choy, vali)],
    )

    by_name = {r["name"]: r for r in result}
    assert [i["name"] for i in by_name["Ali"]["items"]] == ["Steyk"]
    assert [i["name"] for i in by_name["Vali"]["items"]] == ["Choy"]


@pytest.mark.parametrize("tax,tip", [("0", "0"), ("1000", "0"), ("0", "1000")])
def test_total_is_always_subtotal_plus_extras(tax, tip):
    ali, vali = person("Ali"), person("Vali")
    steak, choy = item("Steyk", "90000"), item("Choy", "30000")

    result = calculate_summary(
        session(tax=tax, tip=tip),
        [steak, choy],
        [ali, vali],
        [claim(steak, ali), claim(choy, vali)],
    )

    for r in result:
        assert r["total"] == r["subtotal"] + r["extras"]
