from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID


def calculate_summary(session, items, people, assignments) -> list[dict]:
    """
    Returns a list of dicts, one per person:
      {person_id, name, items: [{name, share}], subtotal, extras, total}

    Tax + tip are split evenly. Each item's line total (price * quantity) is
    divided among the people who claimed it, in proportion to the quantity each
    one claimed. This means the full line total is always distributed, even if
    the claimed quantities don't add up to the item's quantity.
    """
    # item_id → list of (person_id, claimed_qty)
    item_claims: dict[UUID, list[tuple[UUID, Decimal]]] = {}
    for a in assignments:
        item_claims.setdefault(a.item_id, []).append(
            (a.person_id, Decimal(str(a.quantity)))
        )

    item_map = {i.id: i for i in items}

    num_people = len(people)
    tax = Decimal(str(session.tax))
    tip = Decimal(str(session.tip))
    per_person_extras = (tax + tip) / num_people if num_people else Decimal("0")

    results = []
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
                {
                    "name": item.name,
                    "share": share.quantize(Decimal("0.01"), ROUND_HALF_UP),
                }
            )
            subtotal += share

        subtotal = subtotal.quantize(Decimal("0.01"), ROUND_HALF_UP)
        extras = per_person_extras.quantize(Decimal("0.01"), ROUND_HALF_UP)
        total = (subtotal + extras).quantize(Decimal("0.01"), ROUND_HALF_UP)

        results.append(
            {
                "person_id": person.id,
                "name": person.name,
                "items": person_items,
                "subtotal": subtotal,
                "extras": extras,
                "total": total,
            }
        )

    return results
