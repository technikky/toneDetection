"""Stage 15: offline license-key verification -- no SaaS account needed
(a local substitute for Keygen/Cryptolens, which both require an internet
connection and a paid account this project doesn't have).

A license key is a small JSON payload (school, seat count, issue/expiry
dates) signed with an Ed25519 private key that only the vendor holds
(generated once, kept in offline-sdk/license-signing-key/ -- gitignored,
never shipped in the app). This module embeds only the *public* key, which
can verify a signature but can't forge one.

Deliberately soft-enforced for now: an unlicensed install still works
fully (this is a beta handed to a few friendly teachers, not a paid
product yet) -- see get_current_license() callers for the "Beta" banner.
Flipping to hard enforcement later is a small, localized change once
there's an actual sales/payment process to issue real keys from.
"""
import base64
import json
from datetime import date
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config import WRITABLE_DIR

# Public half of the vendor's Ed25519 signing key. Safe to embed -- this can
# only *verify* a signature, not create a new valid license key.
PUBLIC_KEY_B64 = "eKCNDECpRYAs3Xsnj_a8UA1iojfE1k2sQlwZwoCZVI4="

LICENSE_FILE = WRITABLE_DIR / "license.txt"

_public_key = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(PUBLIC_KEY_B64))


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def parse_and_verify(key_str: str) -> Optional[dict]:
    """Returns the license payload dict if key_str is a validly-signed,
    unexpired license key; None otherwise (malformed, tampered, or expired)."""
    key_str = key_str.strip()
    if not key_str.startswith("SSING-") or "." not in key_str:
        return None
    body = key_str[len("SSING-"):]
    try:
        payload_b64, sig_b64 = body.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)
        _public_key.verify(signature, payload_bytes)
        payload = json.loads(payload_bytes)
    except (InvalidSignature, ValueError, KeyError, json.JSONDecodeError):
        return None

    expires = payload.get("expires")
    if expires and date.fromisoformat(expires) < date.today():
        return None
    return payload


def save_license_key(key_str: str) -> bool:
    payload = parse_and_verify(key_str)
    if not payload:
        return False
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(key_str.strip(), encoding="utf-8")
    return True


def get_current_license() -> Optional[dict]:
    if not LICENSE_FILE.exists():
        return None
    return parse_and_verify(LICENSE_FILE.read_text(encoding="utf-8"))
