"""Who may do what in the admin panel.

The rules worth pinning down are the ones that would hand someone rights
nobody granted: a demoted admin keeping theirs, a stale key from an older
build reading back as a grant, or the owner account's implicit rights being
read from a column that could say otherwise.
"""

import pytest

from app.permissions import ALL_PERMISSIONS, Permission, clean
from app.services import admin_auth
from app.services.admin_auth import permissions_of


class FakeRow:
    def __init__(self, is_admin=False, permissions=None):
        self.is_admin = is_admin
        self.permissions = permissions


class FakeDb:
    """Stands in for the session; permissions_of only ever does a get()."""

    def __init__(self, row=None):
        self._row = row

    def get(self, _model, _pk):
        return self._row


@pytest.fixture
def owner(monkeypatch):
    """Make a known id the super admin, whatever the environment says."""
    monkeypatch.setattr(admin_auth.settings, "admin_telegram_ids", "777")
    return 777


# ── The catalog ─────────────────────────────────────────────────────────


def test_the_permission_keys_are_what_the_panel_was_built_against():
    """Renaming one silently strands the grants already in the column and
    the checkboxes in the frontend, which carries this list by hand."""
    assert ALL_PERMISSIONS == {
        "subscriptions",
        "block_users",
        "payments",
        "sessions",
        "tables",
        "manage_admins",
    }


def test_clean_drops_anything_this_build_does_not_define():
    """A permission removed in a later build leaves rows naming it; reading
    that back would revive something deliberately taken out."""
    assert clean(["payments", "launch_missiles"]) == ["payments"]


def test_clean_is_sorted_and_deduplicated():
    assert clean(["tables", "payments", "payments"]) == ["payments", "tables"]


def test_clean_handles_a_column_that_has_never_been_set():
    assert clean(None) == []


# ── Who holds them ──────────────────────────────────────────────────────


def test_the_owner_holds_everything_without_the_column_being_read(owner):
    """Their row may not even exist — that is the point of the fixed id."""
    assert permissions_of(FakeDb(None), owner) == set(ALL_PERMISSIONS)


def test_the_owner_holds_everything_even_if_the_column_says_otherwise(owner):
    db = FakeDb(FakeRow(is_admin=False, permissions=[]))
    assert permissions_of(db, owner) == set(ALL_PERMISSIONS)


def test_an_admin_holds_what_the_column_grants(owner):
    db = FakeDb(FakeRow(is_admin=True, permissions=["payments", "tables"]))
    assert permissions_of(db, 5) == {"payments", "tables"}


def test_a_demoted_admin_holds_nothing_the_column_still_remembers(owner):
    """Demotion clears the column, but the check doesn't depend on that
    having happened — is_admin is the gate."""
    db = FakeDb(FakeRow(is_admin=False, permissions=["manage_admins"]))
    assert permissions_of(db, 5) == set()


def test_someone_with_no_row_at_all_holds_nothing(owner):
    assert permissions_of(FakeDb(None), 5) == set()


def test_an_admin_with_no_grants_holds_nothing(owner):
    db = FakeDb(FakeRow(is_admin=True, permissions=[]))
    assert permissions_of(db, 5) == set()


def test_every_permission_is_reachable_as_an_enum_value():
    assert {p.value for p in Permission} == ALL_PERMISSIONS
