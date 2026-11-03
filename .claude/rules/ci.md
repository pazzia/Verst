---
paths:
  - ".github/workflows/**"
  - "tools/ci/**"
---

# CI rules

- `android.yml` is dispatched by hand on the working branch (`workflow_dispatch`). `main` publishes
  `verst-latest`; working branches publish `verst-test-latest`. Release tags use `--target` on the default branch
  (a `GITHUB_TOKEN` cannot create refs on a history that changes workflows).
- Release notes come from `tools/ci/whats_new.py`, which reads the `Тестерам:` trailers. Keep the notes Russian
  and short.
- Never print secrets; signing material only from GitHub Secrets.
- A red build is work now. A flake is not a root cause: re-run once only to confirm, then fix.
- **APK size budget (D-IR-26):** 45 MB warn, 60 MB fail. Raising it needs the CEO's permission first, with the
  measured size added, evidence that it improves the app, and why it cannot live on the server.
