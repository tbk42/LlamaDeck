from __future__ import annotations

import base64
import os
import sqlite3
import threading
from pathlib import Path

from backend.config import CONFIG_DIR

_local = threading.local()
_encryption_key: bytes | None = None
_key_lock = threading.Lock()

CRED_DB = CONFIG_DIR / "credentials.db"
SALT_FILE = CONFIG_DIR / ".credential_salt"
SECRET_FILE = CONFIG_DIR / ".credential_secret"


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(CRED_DB))
        if not CRED_DB.exists() or CRED_DB.stat().st_mode & 0o777 != 0o600:
            CRED_DB.chmod(0o600)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute(
            """CREATE TABLE IF NOT EXISTS credentials (
                service TEXT PRIMARY KEY,
                encrypted_key TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
    return _local.conn


def _derive_key(secret: bytes, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(secret))


def _get_encryption_key() -> bytes:
    global _encryption_key
    if _encryption_key is not None:
        return _encryption_key

    with _key_lock:
        if _encryption_key is not None:
            return _encryption_key

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        if not SALT_FILE.exists():
            salt = os.urandom(16)
            SALT_FILE.write_bytes(salt)
            SALT_FILE.chmod(0o600)
        else:
            salt = SALT_FILE.read_bytes()

        if not SECRET_FILE.exists():
            import secrets
            secret = secrets.token_bytes(32)
            SECRET_FILE.write_bytes(secret)
            SECRET_FILE.chmod(0o600)
            machine_secret = secret
        else:
            machine_secret = SECRET_FILE.read_bytes()

        _encryption_key = _derive_key(machine_secret, salt)
        return _encryption_key


def _encrypt(plaintext: str) -> str:
    from cryptography.fernet import Fernet

    f = Fernet(_get_encryption_key())
    return f.encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    from cryptography.fernet import Fernet

    f = Fernet(_get_encryption_key())
    return f.decrypt(ciphertext.encode()).decode()


def get_key(service: str) -> str | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT encrypted_key FROM credentials WHERE service = ?", (service,)
    ).fetchone()
    if row is None:
        return None
    try:
        return _decrypt(row["encrypted_key"])
    except Exception:
        return None


def set_key(service: str, key: str) -> None:
    encrypted = _encrypt(key)
    conn = _get_conn()
    conn.execute(
        """INSERT INTO credentials (service, encrypted_key, created_at, updated_at)
           VALUES (?, ?, datetime('now'), datetime('now'))
           ON CONFLICT(service) DO UPDATE SET
               encrypted_key = excluded.encrypted_key,
               updated_at = datetime('now')""",
        (service, encrypted),
    )
    conn.commit()


def delete_key(service: str) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM credentials WHERE service = ?", (service,))
    conn.commit()


def list_services() -> list[str]:
    conn = _get_conn()
    rows = conn.execute("SELECT service FROM credentials ORDER BY service").fetchall()
    return [r["service"] for r in rows]
