"""Tests for user accounts, password handling and sessions.

These cover security properties rather than just happy paths: a regression in
any of them silently weakens authentication, which is not the kind of thing a
smoke test would catch.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_root_dir = str(Path(__file__).resolve().parent.parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from saleha.core.user_store import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_USER,
    AuthenticationError,
    UserStore,
    UserStoreError,
)

GOOD_PASSWORD = "correct-horse-battery"


class UserStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.users_path = os.path.join(self.tmp, "users.json")
        self.sessions_path = os.path.join(self.tmp, "sessions.json")
        self.store = UserStore(self.users_path, self.sessions_path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- accounts

    def test_create_user_normalises_username_and_sets_role(self):
        user = self.store.create_user("  Alice  ", GOOD_PASSWORD, ROLE_ADMIN)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.role, ROLE_ADMIN)
        self.assertTrue(self.store.has_users())

    def test_public_dict_never_exposes_credentials(self):
        user = self.store.create_user("alice", GOOD_PASSWORD)
        exposed = user.to_dict()
        for secret_field in ("salt", "password_hash", "password", "iterations", "kdf"):
            self.assertNotIn(secret_field, exposed)

    def test_duplicate_username_is_rejected(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        with self.assertRaises(UserStoreError):
            self.store.create_user("ALICE", "another-long-password")

    def test_short_password_is_rejected(self):
        with self.assertRaises(UserStoreError):
            self.store.create_user("alice", "short")

    def test_invalid_role_is_rejected(self):
        with self.assertRaises(UserStoreError):
            self.store.create_user("alice", GOOD_PASSWORD, "superuser")

    # ------------------------------------------------------------- at rest

    def test_password_is_not_recoverable_from_disk(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        stored = Path(self.users_path).read_text(encoding="utf-8")
        self.assertNotIn(GOOD_PASSWORD, stored)

    def test_each_user_gets_a_distinct_salt(self):
        """A shared salt would let one precomputation attack every account."""
        self.store.create_user("alice", GOOD_PASSWORD)
        self.store.create_user("bob", GOOD_PASSWORD)
        import json

        records = json.loads(Path(self.users_path).read_text(encoding="utf-8"))
        self.assertNotEqual(records["alice"]["salt"], records["bob"]["salt"])
        # Identical passwords must not produce identical hashes.
        self.assertNotEqual(records["alice"]["password_hash"], records["bob"]["password_hash"])

    def test_session_token_is_not_stored_in_plaintext(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        session = self.store.authenticate("alice", GOOD_PASSWORD)
        stored = Path(self.sessions_path).read_text(encoding="utf-8")
        self.assertNotIn(session.token, stored)

    # ------------------------------------------------------ authentication

    def test_correct_password_issues_a_resolvable_session(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        session = self.store.authenticate("alice", GOOD_PASSWORD)
        resolved = self.store.resolve_session(session.token)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.username, "alice")

    def test_wrong_password_is_rejected(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        with self.assertRaises(AuthenticationError):
            self.store.authenticate("alice", "wrong-password-entirely")

    def test_unknown_user_and_wrong_password_report_the_same_message(self):
        """Distinguishing the two would let an attacker enumerate accounts."""
        self.store.create_user("alice", GOOD_PASSWORD)
        with self.assertRaises(AuthenticationError) as unknown:
            self.store.authenticate("nobody", GOOD_PASSWORD)
        with self.assertRaises(AuthenticationError) as wrong:
            self.store.authenticate("alice", "wrong-password-entirely")
        self.assertEqual(str(unknown.exception), str(wrong.exception))

    def test_repeated_failures_trigger_a_lockout(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        for _ in range(5):
            with self.assertRaises(AuthenticationError):
                self.store.authenticate("alice", "wrong-password-entirely")
        # Even the correct password is refused while locked out.
        with self.assertRaises(AuthenticationError) as locked:
            self.store.authenticate("alice", GOOD_PASSWORD)
        self.assertIn("Too many failed attempts", str(locked.exception))

    def test_unknown_session_token_resolves_to_nothing(self):
        self.assertIsNone(self.store.resolve_session("not-a-real-token"))
        self.assertIsNone(self.store.resolve_session(""))

    def test_expired_session_is_refused(self):
        store = UserStore(self.users_path, self.sessions_path, session_ttl_seconds=-1)
        store.create_user("alice", GOOD_PASSWORD)
        session = store.authenticate("alice", GOOD_PASSWORD)
        self.assertIsNone(store.resolve_session(session.token))

    # ----------------------------------------------------------- lifecycle

    def test_logout_revokes_the_session(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        session = self.store.authenticate("alice", GOOD_PASSWORD)
        self.assertTrue(self.store.revoke_session(session.token))
        self.assertIsNone(self.store.resolve_session(session.token))

    def test_password_change_revokes_existing_sessions(self):
        self.store.create_user("alice", GOOD_PASSWORD)
        session = self.store.authenticate("alice", GOOD_PASSWORD)
        self.store.set_password("alice", "a-brand-new-passphrase")
        self.assertIsNone(self.store.resolve_session(session.token))
        with self.assertRaises(AuthenticationError):
            self.store.authenticate("alice", GOOD_PASSWORD)

    def test_role_change_applies_to_existing_sessions_immediately(self):
        """A demotion must take effect at once, not when the session expires."""
        self.store.create_user("alice", GOOD_PASSWORD, ROLE_ADMIN)
        self.store.create_user("bob", GOOD_PASSWORD, ROLE_ADMIN)
        session = self.store.authenticate("bob", GOOD_PASSWORD)
        self.assertEqual(self.store.resolve_session(session.token).role, ROLE_ADMIN)
        self.store.set_role("bob", ROLE_USER)
        self.assertEqual(self.store.resolve_session(session.token).role, ROLE_USER)

    def test_deleted_user_cannot_keep_using_a_session(self):
        self.store.create_user("alice", GOOD_PASSWORD, ROLE_ADMIN)
        self.store.create_user("bob", GOOD_PASSWORD)
        session = self.store.authenticate("bob", GOOD_PASSWORD)
        self.store.delete_user("bob")
        self.assertIsNone(self.store.resolve_session(session.token))

    def test_last_admin_cannot_be_demoted_or_deleted(self):
        self.store.create_user("alice", GOOD_PASSWORD, ROLE_ADMIN)
        with self.assertRaises(UserStoreError):
            self.store.set_role("alice", ROLE_USER)
        with self.assertRaises(UserStoreError):
            self.store.delete_user("alice")

    def test_admin_can_be_demoted_when_another_admin_remains(self):
        self.store.create_user("alice", GOOD_PASSWORD, ROLE_ADMIN)
        self.store.create_user("bob", GOOD_PASSWORD, ROLE_ADMIN)
        self.assertEqual(self.store.set_role("bob", ROLE_USER).role, ROLE_USER)


if __name__ == "__main__":
    unittest.main()
