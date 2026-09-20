from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from uuid import UUID

CENT = Decimal("0.01")


def _allocate(
    total: Decimal, weights: list[Decimal], tie_break: list[int] | None = None
) -> list[Decimal]:
    """Split `total` across `weights` proportionally, in whole cents."""
    return _allocate_detailed(total, weights, tie_break)[0]


def _allocate_detailed(
    total: Decimal, weights: list[Decimal], tie_break: list[int] | None = None
) -> tuple[list[Decimal], list[int]]:
    """Split `total` in whole cents, and say who got the spare ones.

    Rounding each share on its own would leave the parts a cent or two off the
    total, so the shares are floored first and the leftover cents handed out
    one at a time, largest fractional remainder first. The result always adds
    back up to `total` exactly.

    On an even split every remainder ties, and a tie has to be broken by
    something. Position alone isn't enough: a bill of four items where only
    two divide unevenly hands both spare cents to whoever sorts first, and
    the table sees three different numbers on a split that promised one.
    `tie_break` lets the caller serve whoever is furthest behind — lower goes
    first — which keeps the spread to a single cent.

    Weights that sum to zero (nobody claimed anything) fall back to an even
    split — the only sensible reading of "nobody ate anything".
    """
    n = len(weights)
    if n == 0:
        return [], []

    weight_sum = sum(weights, Decimal("0"))
    if weight_sum <= 0:
        weights = [Decimal("1")] * n
        weight_sum = Decimal(n)

    total = total.quantize(CENT, ROUND_HALF_UP)
    exact = [total * w / weight_sum for w in weights]
    shares = [e.quantize(CENT, ROUND_DOWN) for e in exact]

    leftover = int((total - sum(shares, Decimal("0"))) / CENT)
    if leftover <= 0:
        return shares, []

    keys = tie_break if tie_break is not None else [0] * n
    order = sorted(range(n), key=lambda i: (-(exact[i] - shares[i]), keys[i], i))
    got = order[:leftover]
    for i in got:
        shares[i] += CENT

    return shares, got


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

    Every division here goes through _allocate, so no step of it can invent or
    lose a cent. Rounding each person's share of an item on its own is what
    would: three people splitting 256457 each owe 85485.666…, and three
    shares rounded up come to a cent more than the receipt — small, but it is
    the table's own arithmetic that disagrees with the app.
    """
    # item_id → list of (person_id, claimed_qty)
    item_claims: dict[UUID, list[tuple[UUID, Decimal]]] = {}
    for a in assignments:
        item_claims.setdefault(a.item_id, []).append(
            (a.person_id, Decimal(str(a.quantity)))
        )

    item_map = {i.id: i for i in items}

    # Per item: the line total, split across its claimers in whole cents. The
    # parts add back to the line exactly, so the subtotals below are already
    # exact and never need rounding of their own.
    person_items: dict[UUID, list[dict]] = {p.id: [] for p in people}
    subtotals: dict[UUID, Decimal] = {p.id: Decimal("0") for p in people}
    # How many spare cents each person has collected so far. The next tie goes
    # to whoever is furthest behind, so an even split stays even.
    spare: dict[UUID, int] = {p.id: 0 for p in people}

    for item_id, claims in item_claims.items():
        total_claimed = sum((q for _, q in claims), Decimal("0"))
        # Nobody actually claimed it: charged to no one, and reported as such
        # by unclaimed_items() rather than spread around silently.
        if total_claimed <= 0:
            continue
        item = item_map[item_id]
        line_total = Decimal(str(item.price)) * Decimal(str(item.quantity))
        shares, got_spare = _allocate_detailed(
            line_total,
            [q for _, q in claims],
            tie_break=[spare.get(pid, 0) for pid, _ in claims],
        )
        for index in got_spare:
            claimer = claims[index][0]
            if claimer in spare:
                spare[claimer] += 1
        for (person_id, qty), share in zip(claims, shares):
            if qty <= 0 or person_id not in person_items:
                continue
            person_items[person_id].append({"name": item.name, "share": share})
            subtotals[person_id] += share

    tax = Decimal(str(session.tax))
    tip = Decimal(str(session.tip))
    # Same rule for the last division: the spare cent on tax and tip goes to
    # whoever has been handed fewest of them.
    extras_each = _allocate(
        tax + tip,
        [subtotals[p.id] for p in people],
        tie_break=[spare[p.id] for p in people],
    )

    return [
        {
            "person_id": person.id,
            "name": person.name,
            "items": person_items[person.id],
            "subtotal": subtotals[person.id],
            "extras": extras,
            "total": subtotals[person.id] + extras,
        }
        for person, extras in zip(people, extras_each)
    ]


def unclaimed_items(items, assignments) -> list[dict]:
    """Items nobody claimed, with the money riding on each one.

    calculate_summary has nobody to charge for these, so it skips them and the
    people's totals quietly add up to less than the receipt. Naming them is
    what lets the host see the gap before finalizing instead of handing out a
    split that's short by the price of the bread.
    """
    claimed = {a.item_id for a in assignments if Decimal(str(a.quantity)) > 0}
    return [
        {
            "item_id": item.id,
            "name": item.name,
            "amount": (Decimal(str(item.price)) * Decimal(str(item.quantity))).quantize(
                CENT, ROUND_HALF_UP
            ),
        }
        for item in items
        if item.id not in claimed
    ]
