"""What an admin is allowed to do.

Admin used to be one bit with a second one bolted on. The owner account saw
everything; anyone promoted from the panel got the overview tab — which is
the user list, and the subscription buttons sitting on every row. So handing
someone the ability to look up a user also handed them the ability to give
away subscriptions, and there was no way to hand over the payments ledger
without handing over everything else too.

These are the things the panel can do, grantable one at a time. Being an
admin at all still buys the overview: the stats and the user list, read-only.
Every action on top of that is named here.

The super admin holds all of them implicitly and is never read from the
column — that is what keeps the panel reachable no matter what anyone
revokes. Labels live in the frontend, which is where the rest of the panel's
Uzbek lives; this module owns the keys.
"""

from enum import StrEnum


class Permission(StrEnum):
    #: Grant and revoke subscriptions, which is money moving.
    SUBSCRIPTIONS = "subscriptions"
    #: Block and unblock users.
    BLOCK_USERS = "block_users"
    #: The payments ledger.
    PAYMENTS = "payments"
    #: The list of bills people have split.
    SESSIONS = "sessions"
    #: Row counts and database size.
    TABLES = "tables"
    #: Promote, demote, and hand out these very permissions. The one that
    #: lets its holder create more admins, so it is worth giving last.
    MANAGE_ADMINS = "manage_admins"


ALL_PERMISSIONS: frozenset[str] = frozenset(p.value for p in Permission)


def clean(values: list[str] | None) -> list[str]:
    """Keep the ones this version knows about, in a stable order.

    A permission dropped from a later build leaves rows behind that still
    name it; reading them back as a grant would be reviving something that
    was deliberately removed.
    """
    known = set(values or []) & ALL_PERMISSIONS
    return sorted(known)
