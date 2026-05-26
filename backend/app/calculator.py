from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID


def calculate_summary(session, items, people, assignments) -> list[dict]:
    """
    Returns a list of dicts, one per person:
      {person_id, name, items: [{name, share}], subtotal, extras, total}

    Tax + tip are split evenly. Shared items are divided equally among assignees.
    """
    # item_id → list of person_ids
    item_assignees: dict[UUID, list[UUID]] = {}
    for a in assignments:
        item_assignees.setdefault(a.item_id, []).append(a.person_id)

    # item_id → Item object
    item_map = {i.id: i for i in items}

    num_people = len(people)
    tax = Decimal(str(session.tax))
    tip = Decimal(str(session.tip))
    per_person_extras = (tax + tip) / num_people if num_people else Decimal("0")

    results = []
    for person in people:
        person_items = []
        subtotal = Decimal("0")

        for item_id, assignee_ids in item_assignees.items():
            if person.id not in assignee_ids:
                continue
            item = item_map[item_id]
            share = (
                Decimal(str(item.price))
                * Decimal(str(item.quantity))
                / Decimal(str(len(assignee_ids)))
            )
            person_items.append({"name": item.name, "share": share.quantize(Decimal("0.01"), ROUND_HALF_UP)})
            subtotal += share

        subtotal = subtotal.quantize(Decimal("0.01"), ROUND_HALF_UP)
        extras = per_person_extras.quantize(Decimal("0.01"), ROUND_HALF_UP)
        total = (subtotal + extras).quantize(Decimal("0.01"), ROUND_HALF_UP)

        results.append({
            "person_id": person.id,
            "name": person.name,
            "items": person_items,
            "subtotal": subtotal,
            "extras": extras,
            "total": total,
        })

    return results
