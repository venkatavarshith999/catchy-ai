# Release history

- `5f46346` — Audit the preserved v1 implementation and record the product upgrade plan.
- `4f73756` — Integrated v2 product beta: phone/family UI, multilingual resources, FastAPI/privacy/contact flows, optional providers, PWA/Android source, tests, deployment and packaging.
- Final release verification — Confirm archive integrity and extracted-copy HTTP startup, route the index alias to the product UI, and repair a missing pip bootstrap on Windows startup.

Git history stays in the development workspace; `.git` is intentionally excluded from the portable ZIP. The initial prototype is preserved in legacy files, while the default launcher starts the v2 service.
