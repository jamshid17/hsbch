"""The join-code pool.

Four digits is ten thousand codes, and they are handed out and taken back
rather than held for good — so the two things worth pinning down are that a
code is only ever handed out when it is free, and that running out is a
refusal rather than a collision.
"""

from datetime import datetime, timedelta, timezone

from app.joincode import ALL_CODES, CODE_LEN, CODE_TTL, lookup_cutoff, pick_free_code


def test_the_pool_is_every_four_digit_code_once():
    assert len(ALL_CODES) == 10_000
    assert len(set(ALL_CODES)) == 10_000
    assert all(len(c) == CODE_LEN and c.isdigit() for c in ALL_CODES)


def test_leading_zeros_are_kept():
    """'0729' is four keystrokes; '729' is a different code that isn't one."""
    assert "0000" in ALL_CODES
    assert "0729" in ALL_CODES


def test_a_free_pool_hands_out_a_real_code():
    assert pick_free_code(set()) in ALL_CODES


def test_a_taken_code_is_never_handed_out():
    taken = set(ALL_CODES) - {"0729"}
    assert pick_free_code(taken) == "0729"


def test_an_exhausted_pool_refuses_rather_than_repeating():
    """The caller turns this into a 503. The old allocator guessed at random
    and gave up after fifty tries, so it could fail with codes still free —
    and, had the unique index ever been dropped without this, collide."""
    assert pick_free_code(set(ALL_CODES)) is None


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_the_window_is_the_ttl_behind_now():
    before = utcnow()
    cutoff = lookup_cutoff()
    after = utcnow()

    assert before - CODE_TTL <= cutoff <= after - CODE_TTL


def test_the_window_is_naive_like_the_column_it_is_compared_against():
    """sessions.created_at is a naive DateTime; comparing an aware value
    against it raises rather than filtering."""
    assert lookup_cutoff().tzinfo is None


def test_the_window_is_long_enough_to_outlast_a_meal():
    assert CODE_TTL >= timedelta(days=1)
