from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from uuid import UUID

CENT = Decimal("0.01")


def _allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across `weights` proportionally, in whole cents.

    Rounding each share on its own would leave the parts a cent or two off the
    total, so the shares are floored first and the leftover cents handed out
    one at a time, largest fractional remainder first. The result always adds
    back up to `total` exactly.

    Weights that sum to zero (nobody claimed anything) fall back to an even
    split — the only sensible reading of "nobody ate anything".
    """
    n = len(weights)
    if n == 0:
        return []

    weight_sum = sum(weights, Decimal("0"))
    if weight_sum <= 0:
        weights = [Decimal("1")] * n
        weight_sum = Decimal(n)

    total = total.quantize(CENT, ROUND_HALF_UP)
    exact = [total * w / weight_sum for w in weights]
    shares = [e.quantize(CENT, ROUND_DOWN) for e in exact]

    leftover = int((total - sum(shares, Decimal("0"))) / CENT)
    if leftover > 0:
        order = sorted(range(n), key=lambda i: exact[i] - shares[i], reverse=True)
        for i in order[:leftover]:
            shares[i] += CENT

    return shares


def calculate_summary(session, items, people, assignments) -> list[dict]:
    """
    Returns a list of dicts, one per person:
      {person_id, name, items: [{name, share}], subtotal, extras, total}

    Each item's line total (price * quantity) is divided among the people who
    claimed it, in proportion to the quantity each one claimed. This means the
    full line total is always distributed, even if the claimed quantities don't
    add up to the item's quantity.

    Tax + tip ride on top of what each person actually ate: someone whose food
    came to 100k carries a proportionally bigger slice of the service fee than
    someone at 30k, instead of the two paying the same flat share.
    """
    # item_id → list of (person_id, claimed_qty)
    item_claims: dict[UUID, list[tuple[UUID, Decimal]]] = {}
    for a in assignments:
        item_claims.setdefault(a.item_id, []).append(
            (a.person_id, Decimal(str(a.quantity)))
        )

    item_map = {i.id: i for i in items}

    # First pass: what everyone owes for their own food, unrounded — that's
    # the weight the extras are shared out by.
    per_person_items: list[list[dict]] = []
    raw_subtotals: list[Decimal] = []

    for person in people:
        person_items = []
        subtotal = Decimal("0")

        for item_id, claims in item_claims.items():
            total_claimed = sum((q for _, q in claims), Decimal("0"))
            if total_claimed <= 0:
                continue
            my_qty = next((q for pid, q in claims if pid == person.id), Decimal("0"))
            if my_qty <= 0:
                continue
            item = item_map[item_id]
            line_total = Decimal(str(item.price)) * Decimal(str(item.quantity))
            share = line_total * (my_qty / total_claimed)
            person_items.append(
                {"name": item.name, "share": share.quantize(CENT, ROUND_HALF_UP)}
            )
            subtotal += share

        per_person_items.append(person_items)
        raw_subtotals.append(subtotal)

    tax = Decimal(str(session.tax))
    tip = Decimal(str(session.tip))
    extras_each = _allocate(tax + tip, raw_subtotals)

    results = []
    for person, person_items, raw_subtotal, extras in zip(
        people, per_person_items, raw_subtotals, extras_each
    ):
        subtotal = raw_subtotal.quantize(CENT, ROUND_HALF_UP)
        results.append(
            {
                "person_id": person.id,
                "name": person.name,
                "items": person_items,
                "subtotal": subtotal,
                "extras": extras,
                "total": (subtotal + extras).quantize(CENT, ROUND_HALF_UP),
            }
        )

    return results
