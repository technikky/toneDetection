"""Stage 15: vendor-side tool to mint a signed offline license key.

Run this yourself when you sell a seat -- it is NOT shipped in the app
(the app only embeds the public key, in app/licensing.py). Requires the
private key generated once into offline-sdk/license-signing-key/ (local
only, gitignored -- back it up somewhere safe; losing it means you can
never issue a key that validates against the public key already embedded
in copies of the app you've distributed).

Usage:
    python scripts/generate_license.py --school "Lincoln Middle School" --seats 30
    python scripts/generate_license.py --school "Lincoln MS" --seats 30 --expires 2027-06-30
"""
import argparse
import base64
import json
import sys
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEY_PATH = REPO_ROOT / "offline-sdk" / "license-signing-key" / "private_key.b64"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--school", required=True, help="School / customer name embedded in the key.")
    parser.add_argument("--seats", type=int, required=True, help="Number of licensed seats.")
    parser.add_argument("--expires", default=None, help="Optional YYYY-MM-DD expiry date.")
    parser.add_argument("--key-file", default=str(DEFAULT_KEY_PATH), help="Path to the private signing key.")
    args = parser.parse_args()

    key_path = Path(args.key_file)
    if not key_path.exists():
        print(f"Private key not found at {key_path}.", file=sys.stderr)
        print("Generate one first (see docs/packaging/LICENSING.md).", file=sys.stderr)
        sys.exit(1)

    private_key = Ed25519PrivateKey.from_private_bytes(
        base64.urlsafe_b64decode(key_path.read_text().strip())
    )

    payload = {
        "school": args.school,
        "seats": args.seats,
        "issued": date.today().isoformat(),
        "expires": args.expires,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload_bytes)

    license_key = f"SSING-{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"
    print(license_key)


if __name__ == "__main__":
    main()
