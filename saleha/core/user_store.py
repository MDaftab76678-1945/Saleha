"""
Saleha user accounts and sessions.

Until now the server had no notion of a user: every caller presented the same
shared ``SALEHA_STUDIO_TOKEN``, which is regenerated on each launch. That is
workable for a single-operator local tool but cannot express "who did this" or
"who may see the admin panel", and nothing built on top of it (per-user limits,
subscriptions) can be honest without real accounts first.

Design notes:

- Hashing is PBKDF2-HMAC-SHA256 from the standard library, matching
  ``saleha/core/vault.py`` so no new cryptographic dependency is introduced.
  Unlike the vault, which derives from one global salt, every user gets their
  own 32-byte salt: a shared salt would let one precomputation attack every
  account at once. The iteration count is stored per record so it can be raised
  later without invalidating existing passwords.
- Session tokens are random 32-byte values. Only their SHA-256 digest is
  written to disk, so someone who reads sessions.json still cannot authenticate
  with what they find there.
- Every secret comparison uses ``secrets.compare_digest``. A login attempt for
  an unknown username still performs a full hash computation, so response
  timing does not reveal which usernames exist.
- Failed-login throttling is in-memory and therefore resets when the server
  restarts. It raises the cost of online guessing; it is not a defence against
  an attacker who can restart the process.

Storage is JSON under ~/.saleha/, consistent with the other stores in this
codebase. Files are created 0600 where the platform honours it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SALEHA_HOME = os.path.join(os.path.expanduser("~"), ".saleha")
DEFAULT_USERS_PATH = os.path.join(SALEHA_HOME, "users.json")
DEFAULT_SESSIONS_PATH = os.path.join(SALEHA_HOME, "sessions.json")

KDF_NAME = "pbkdf2_hmac_sha256"
DEFAULT_ITERATIONS = 200_000
SALT_BYTES = 32
SESSION_TOKEN_BYTES = 32
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60

ROLE_ADMIN = "admin"
ROLE_USER = "user"
VALID_ROLES = (ROLE_ADMIN, ROLE_USER)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


class UserStoreError(Exception):
    """Raised for expected, reportable problems such as a duplicate username."""


class AuthenticationError(Exception):
    """Raised when credentials are rejected. The message is deliberately vague."""


@dataclass
class User:
    id: str
    username: str
    role: str
    created_at: str
    last_login_at: Optional[str] = None
    disabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Public representation. Never includes salt or hash."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
            "disabled": self.disabled,
        }


@dataclass
class Session:
    token: str
    user: User
    expires_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "expires_at": self.expires_at,
            "user": self.user.to_dict(),
        }


@dataclass
class _Throttle:
    failures: int = 0
    locked_until: float = 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_private(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    try:
        # Best effort: Windows ignores the mode bits, POSIX honours them.
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    os.replace(tmp_path, path)


def _read_json(path: str, fallback: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def hash_password(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UserStore:
    def __init__(
        self,
        users_path: str = DEFAULT_USERS_PATH,
        sessions_path: str = DEFAULT_SESSIONS_PATH,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ):
        self.users_path = users_path
        self.sessions_path = sessions_path
        self.session_ttl_seconds = session_ttl_seconds
        self._throttles: Dict[str, _Throttle] = {}

    # ---------------------------------------------------------------- users

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        data = _read_json(self.users_path, {})
        return data if isinstance(data, dict) else {}

    def _save_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        _write_json_private(self.users_path, users)

    @staticmethod
    def _normalise(username: str) -> str:
        return username.strip().lower()

    def has_users(self) -> bool:
        return bool(self._load_users())

    def list_users(self) -> List[User]:
        users = [self._record_to_user(record) for record in self._load_users().values()]
        users.sort(key=lambda u: u.username)
        return users

    def get_user(self, username: str) -> Optional[User]:
        record = self._load_users().get(self._normalise(username))
        return self._record_to_user(record) if record else None

    @staticmethod
    def _record_to_user(record: Dict[str, Any]) -> User:
        return User(
            id=record.get("id", ""),
            username=record.get("username", ""),
            role=record.get("role", ROLE_USER),
            created_at=record.get("created_at", ""),
            last_login_at=record.get("last_login_at"),
            disabled=bool(record.get("disabled", False)),
        )

    def create_user(self, username: str, password: str, role: str = ROLE_USER) -> User:
        key = self._normalise(username)
        if not key:
            raise UserStoreError("Username must not be empty.")
        if role not in VALID_ROLES:
            raise UserStoreError(f"Role must be one of {', '.join(VALID_ROLES)}.")
        problem = self.password_problem(password)
        if problem:
            raise UserStoreError(problem)

        users = self._load_users()
        if key in users:
            raise UserStoreError(f"User '{key}' already exists.")

        salt = secrets.token_bytes(SALT_BYTES)
        users[key] = {
            "id": str(uuid.uuid4()),
            "username": key,
            "role": role,
            "kdf": KDF_NAME,
            "iterations": DEFAULT_ITERATIONS,
            "salt": salt.hex(),
            "password_hash": hash_password(password, salt).hex(),
            "created_at": _now_iso(),
            "last_login_at": None,
            "disabled": False,
        }
        self._save_users(users)
        return self._record_to_user(users[key])

    @staticmethod
    def password_problem(password: str) -> Optional[str]:
        """Returns why a password is unacceptable, or None if it is fine."""
        if password is None or len(password) < 10:
            return "Password must be at least 10 characters."
        if password.strip() == "":
            return "Password must not be only whitespace."
        return None

    def set_password(self, username: str, new_password: str) -> None:
        problem = self.password_problem(new_password)
        if problem:
            raise UserStoreError(problem)
        users = self._load_users()
        key = self._normalise(username)
        record = users.get(key)
        if not record:
            raise UserStoreError(f"No such user: {key}")
        salt = secrets.token_bytes(SALT_BYTES)
        record["salt"] = salt.hex()
        record["iterations"] = DEFAULT_ITERATIONS
        record["kdf"] = KDF_NAME
        record["password_hash"] = hash_password(new_password, salt).hex()
        self._save_users(users)
        # A password change must not leave old sessions usable.
        self.revoke_all_for_user(record["id"])

    def set_role(self, username: str, role: str) -> User:
        if role not in VALID_ROLES:
            raise UserStoreError(f"Role must be one of {', '.join(VALID_ROLES)}.")
        users = self._load_users()
        key = self._normalise(username)
        record = users.get(key)
        if not record:
            raise UserStoreError(f"No such user: {key}")
        if record.get("role") == ROLE_ADMIN and role != ROLE_ADMIN and self._admin_count(users) <= 1:
            raise UserStoreError("Refusing to demote the only remaining admin.")
        record["role"] = role
        self._save_users(users)
        return self._record_to_user(record)

    def delete_user(self, username: str) -> None:
        users = self._load_users()
        key = self._normalise(username)
        record = users.get(key)
        if not record:
            raise UserStoreError(f"No such user: {key}")
        if record.get("role") == ROLE_ADMIN and self._admin_count(users) <= 1:
            raise UserStoreError("Refusing to delete the only remaining admin.")
        del users[key]
        self._save_users(users)
        self.revoke_all_for_user(record["id"])

    @staticmethod
    def _admin_count(users: Dict[str, Dict[str, Any]]) -> int:
        return sum(1 for r in users.values() if r.get("role") == ROLE_ADMIN and not r.get("disabled"))

    # ------------------------------------------------------- authentication

    def _throttle_state(self, key: str) -> _Throttle:
        return self._throttles.setdefault(key, _Throttle())

    def authenticate(self, username: str, password: str) -> Session:
        key = self._normalise(username)
        throttle = self._throttle_state(key)
        now = time.time()

        if throttle.locked_until > now:
            wait = int(throttle.locked_until - now)
            raise AuthenticationError(
                f"Too many failed attempts. Try again in {wait} seconds."
            )

        users = self._load_users()
        record = users.get(key)

        # An unknown username still runs a full derivation so that the time
        # taken does not reveal whether the account exists.
        if record is None:
            decoy_salt = secrets.token_bytes(SALT_BYTES)
            hash_password(password or "", decoy_salt)
            self._register_failure(throttle)
            raise AuthenticationError("Invalid username or password.")

        if record.get("disabled"):
            raise AuthenticationError("This account is disabled.")

        salt = bytes.fromhex(record.get("salt", ""))
        iterations = int(record.get("iterations", DEFAULT_ITERATIONS))
        expected = bytes.fromhex(record.get("password_hash", ""))
        candidate = hash_password(password or "", salt, iterations)

        if not hmac.compare_digest(candidate, expected):
            self._register_failure(throttle)
            raise AuthenticationError("Invalid username or password.")

        throttle.failures = 0
        throttle.locked_until = 0.0

        record["last_login_at"] = _now_iso()
        self._save_users(users)

        return self._issue_session(self._record_to_user(record))

    @staticmethod
    def _register_failure(throttle: _Throttle) -> None:
        throttle.failures += 1
        if throttle.failures >= MAX_FAILED_ATTEMPTS:
            throttle.locked_until = time.time() + LOCKOUT_SECONDS
            throttle.failures = 0

    # ------------------------------------------------------------- sessions

    def _load_sessions(self) -> Dict[str, Dict[str, Any]]:
        data = _read_json(self.sessions_path, {})
        return data if isinstance(data, dict) else {}

    def _save_sessions(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        _write_json_private(self.sessions_path, sessions)

    def _issue_session(self, user: User) -> Session:
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        expires_at = time.time() + self.session_ttl_seconds
        sessions = self._prune(self._load_sessions())
        sessions[_hash_session_token(token)] = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "expires_at": expires_at,
            "created_at": _now_iso(),
        }
        self._save_sessions(sessions)
        return Session(token=token, user=user, expires_at=expires_at)

    @staticmethod
    def _prune(sessions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        now = time.time()
        return {
            digest: record
            for digest, record in sessions.items()
            if float(record.get("expires_at", 0)) > now
        }

    def resolve_session(self, token: str) -> Optional[User]:
        """Returns the user for a session token, or None if it is unknown or expired."""
        if not token:
            return None
        sessions = self._load_sessions()
        record = sessions.get(_hash_session_token(token))
        if not record:
            return None
        if float(record.get("expires_at", 0)) <= time.time():
            return None

        # Read the live user so a role change or deletion takes effect at once
        # rather than lingering until the session expires.
        users = self._load_users()
        user_record = users.get(str(record.get("username", "")))
        if not user_record or user_record.get("disabled"):
            return None
        return self._record_to_user(user_record)

    def revoke_session(self, token: str) -> bool:
        sessions = self._load_sessions()
        digest = _hash_session_token(token)
        if digest not in sessions:
            return False
        del sessions[digest]
        self._save_sessions(sessions)
        return True

    def revoke_all_for_user(self, user_id: str) -> int:
        sessions = self._load_sessions()
        remaining = {d: r for d, r in sessions.items() if r.get("user_id") != user_id}
        removed = len(sessions) - len(remaining)
        if removed:
            self._save_sessions(remaining)
        return removed

    def active_session_count(self) -> int:
        return len(self._prune(self._load_sessions()))


user_store = UserStore()
