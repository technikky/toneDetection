# Offline licensing (vendor-side notes)

Sight-Singing Studio uses a self-contained, offline license-key scheme
instead of a paid SaaS licensing service (Keygen, Cryptolens, etc.) --
those require an internet connection at verification time and a paid
account, both of which conflict with this app's offline design and the
fact that there's no billing/sales infrastructure set up yet.

## How it works

A license key is a small JSON payload (school name, seat count, issue
date, optional expiry) signed with an **Ed25519** private key. The app
only embeds the corresponding **public** key (`app/licensing.py`,
`PUBLIC_KEY_B64`), which can verify a signature but never create a new
valid one. This means:

- Verification is entirely local -- no network call, no account.
- Only whoever holds the private key can mint a license key that any
  distributed copy of the app will accept.

## The private key

Generated once into `offline-sdk/license-signing-key/private_key.b64`
(base64, raw 32 bytes) -- **gitignored, never committed, never shipped in
the app or the installer.**

**Back this file up somewhere durable and secure (a password manager's
secure notes, an encrypted archive, etc.).** If it's lost, you cannot
issue new valid license keys without changing the public key embedded in
`app/licensing.py` -- which means rebuilding and redistributing the app,
and every previously-issued key becomes worthless since it was signed
with the old private key.

If you need to regenerate the keypair from scratch:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64

private_key = Ed25519PrivateKey.generate()
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)
public_bytes = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
print("private (save to offline-sdk/license-signing-key/private_key.b64):",
      base64.urlsafe_b64encode(private_bytes).decode())
print("public (paste into app/licensing.py PUBLIC_KEY_B64):",
      base64.urlsafe_b64encode(public_bytes).decode())
```

## Issuing a key to a customer

```powershell
python scripts\generate_license.py --school "Lincoln Middle School" --seats 30
python scripts\generate_license.py --school "Lincoln MS" --seats 30 --expires 2027-06-30
```

Prints the license key string to stdout. Send that to the customer; they
paste it into `/teacher/license` in the app.

## Current enforcement level: soft

An unlicensed install is **fully functional** right now -- the app just
shows a "Beta / Unlicensed" badge instead of "Licensed". This is
deliberate: there's no real sales process yet, so hard-blocking beta
testers who don't have a key would be counterproductive. `licensing.get_current_license()`
already returns everything needed (school, seats, expiry) to add hard
enforcement later -- e.g. gating student-roster size to the licensed seat
count -- once there's an actual product to sell.
