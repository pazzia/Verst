---
paths:
  - "backend/api/**"
  - "infra/**"
---

# Server rules

- **Privacy (R-07, 152-FZ).**
  - No table or log holds an exact coordinate, a typed address, an IP or a device id other than our own random one.
  - Logs carry `device_tag`, never the token.
  - Free text is masked and expires (`VERST_FEEDBACK_TEXT_DAYS`).
- **Secrets** only from the environment (`.env` on the server, `SecretStr` in `Settings`). Never in code, logs,
  `.env.example` or docs. New settings go into `infra/api/.env.example` with an empty value and a comment.
- **Partners and upstreams fail soft:** a partner API (Travelpayouts) or GraphHopper failure falls back
  (plain link, road model), never a 500 for the user.
- **Checks:** `cd backend/api && python3 -m pytest -q && ruff check verst_api tests && python3 -m mypy verst_api tests`.
- **The CEO runs every server command.** Give the commands one per code block. Update `docs/ops/test-server.md`
  when a setting, path or command changes.
- The NL VM is for tests only; nothing here may assume production data.
