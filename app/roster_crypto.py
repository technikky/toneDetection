"""Stage 15: field-level encryption for the student roster's real names.

Local-only (no cloud KMS): a symmetric key is generated on first run and
stored outside version control, next to the database. Anyone with
filesystem access to the app's data directory *and* the key file can
decrypt -- this protects against casual disclosure (e.g. a stolen backup
of just the .db file, or someone browsing the SQLite file directly) but
is not a substitute for full-disk encryption or restricting who can log
into the machine at all.
"""
import os

from cryptography.fernet import Fernet

from app.config import DB_PATH

_KEY_PATH = DB_PATH.parent / ".roster_key"
_fernet: "Fernet | None" = None


def _load_or_create_key() -> bytes:
    if _KEY_PATH.exists():
        return _KEY_PATH.read_bytes()
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    _KEY_PATH.write_bytes(key)
    try:
        os.chmod(_KEY_PATH, 0o600)
    except OSError:
        pass  # best-effort; Windows ACLs aren't chmod-controlled
    return key


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt_name(name: str) -> bytes:
    return _get_fernet().encrypt(name.encode("utf-8"))


def decrypt_name(token: bytes) -> str:
    return _get_fernet().decrypt(bytes(token)).decode("utf-8")
