"""What counts as a receipt.

Scanning a photo that isn't one used to produce a bill with nothing in it,
and the person found out two screens later at "add at least one item" —
by which point there is no telling which photo was the problem. This is the
check that turns that into an answer on the scan screen.
"""

from decimal import Decimal

import pytest

from app.schemas import ScanResult, ScannedItem
from app.services.vision import ReceiptScanError, _reject_if_not_a_receipt


def result(is_receipt=True, prices=("50000",)):
    return ScanResult(
        is_receipt=is_receipt,
        title="Istanbul",
        currency="so'm",
        tax=Decimal("0"),
        tip=Decimal("0"),
        items=[
            ScannedItem(name=f"Taom {i}", price=Decimal(p))
            for i, p in enumerate(prices)
        ],
    )


def test_a_real_receipt_passes():
    _reject_if_not_a_receipt(result())


def test_the_model_saying_it_is_not_one_is_taken_at_its_word():
    """The prompt offers this answer precisely so it never has to invent
    line items to fill the shape it was asked for."""
    with pytest.raises(ReceiptScanError) as exc:
        _reject_if_not_a_receipt(result(is_receipt=False, prices=()))

    assert exc.value.code == "scan.not_a_receipt"


def test_an_empty_bill_is_refused_even_when_the_model_insists():
    """A reply with no items is a receipt in shape only — the backstop for a
    model that ignores the flag."""
    with pytest.raises(ReceiptScanError) as exc:
        _reject_if_not_a_receipt(result(prices=()))

    assert exc.value.code == "scan.not_a_receipt"


def test_a_bill_of_nothing_but_zero_prices_is_refused():
    """Nothing to split, and a menu photographed as a receipt reads like
    this when the prices don't come through."""
    with pytest.raises(ReceiptScanError):
        _reject_if_not_a_receipt(result(prices=("0", "0")))


def test_one_priced_item_among_zeroes_is_enough():
    """Free items on a real bill — a complimentary tea — are ordinary, and
    the rest of the receipt is still worth splitting."""
    _reject_if_not_a_receipt(result(prices=("0", "45000")))


def test_the_refusal_is_a_sentence_the_user_can_act_on():
    with pytest.raises(ReceiptScanError) as exc:
        _reject_if_not_a_receipt(result(is_receipt=False, prices=()))

    assert "chek" in str(exc.value).lower()
