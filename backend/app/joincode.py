"""The four-digit code people read off the screen and type to join a bill.

Four digits is what someone can read out across a table without a typo, and
that caps the pool at ten thousand. Sessions used to hold a code for good, so
the ten-thousandth bill ever created would have found nothing left to take
and the allocator would have started answering 500 — quietly, for everyone.

So codes are recycled, and the same window governs both halves of that:

  * a code is *taken* only by sessions newer than the window, so anything
    older frees its code back into the pool;
  * a code *resolves* only to sessions newer than the window, so a link or a
    share button carrying an expired code finds nothing at all, rather than
    finding whichever bill holds that code now.

The second half is what makes the first one safe. Anything that has to
outlive the window — a deep link posted into a chat — carries the session id
instead, which is never reused.
"""

import secrets
from datetime import datetime, timedelta, timezone

CODE_LEN = 4

# Every code there is, as the strings they're stored as.
ALL_CODES = tuple(str(n).zfill(CODE_LEN) for n in range(10**CODE_LEN))

# Far longer than a restaurant bill stays interesting, short enough that the
# pool never empties.
CODE_TTL = timedelta(days=30)


def lookup_cutoff() -> datetime:
    """Sessions created after this still answer to their code.

    Naive UTC, matching how every timestamp in this schema is stored — read
    from an aware clock and stripped, the way timeutil does it, rather than
    through the deprecated utcnow().
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return now - CODE_TTL


def pick_free_code(taken: set[str]) -> str | None:
    """A code none of `taken` is using, or None once they all are.

    Chosen from the codes actually free rather than guessed at random, so
    allocation doesn't start failing by chance as the pool fills: it works
    until the pool is genuinely empty, and then says so.
    """
    free = [code for code in ALL_CODES if code not in taken]
    return secrets.choice(free) if free else None
