# ADR-0007: Anonymous device authentication with opaque bearer tokens

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §2, §12, §16 (152-FZ); architecture §9.2, §10.1, §10.8, §11.6

## Context
The MVP has no accounts and must collect no personal data, yet the API needs per-device rate limits (30 plans/hour), trip ownership, saved trips and attribution of feedback and waitlist entries.

## Decision
On first launch the app calls `POST /v1/devices {appVersion, locale}` and receives `{deviceId, token}`. The token is 32 random bytes (base64url); the server stores only `sha256(token)` in `app.device.token_hash`. Every request sends `Authorization: Bearer <token>`. The token is kept in a separate DataStore file excluded from Android backup, so a reinstall creates a new device (SPEC §16 "rotated on reinstall"). On 401 the app re-registers once silently. No IMEI/advertising ID/Android ID is collected. Abuse control: per-device and per-IP (nginx) rate limits; device registration limited to 20/hour/IP.

## Consequences
- Zero sign-up; no personal data stored (privacy policy can state it).
- Saved trips live on the device; the server copy is reachable only with the token or the public share slug. Reinstall loses server-side ownership of old trips (acceptable: offline copies are local and lost on uninstall anyway; cloud sync is out of scope).
- Tokens are long-lived; revocation by setting `revoked_at`.

## Alternatives
- **JWT** — no benefit without an identity provider; revocation harder.
- **Android ID / Play Integrity** — personal-data concerns and GMS dependency (RuStore devices).
- **No auth, IP-only limits** — cannot enforce trip ownership or per-device limits behind mobile CGNAT.
