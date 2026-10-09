# Verification record

Verified during the build on 9-10 October 2026:

- Python compilation and JavaScript syntax checks passed.
- 17 Python tests passed: real HTTP/API requests, account isolation, passwords/login/logout, consent validation, contact ownership, retention/deletion, request bounds, throttling, detector behavior and mocked model validation/fallback.
- 10 guest JavaScript detector regression scenarios passed.
- The 12-case synthetic development evaluation ran. Ten cases matched expectations. Unseen paraphrasing and quotation of a past scam are intentionally recorded weaknesses. These results do not establish real-world accuracy.

Verification limits:

- The server started and in-process HTTP integration tests passed. A separate browser preview could not reach the server in this environment, including after network permission was granted. Visual browser QA and UI interaction testing are not claimed as completed.
- Docker CLI is available but its daemon is not running. Container execution was not locally verified. CI includes a build and health smoke test.
- No real Ollama model service, microphone, dialer or speech synthesis was exercised. Model validation and failure behavior used controlled responses.
- GitHub workflows are supplied, not remotely executed. Deployment requires repository and host setup.

Before presenting, run the app in your presentation browser, inspect all six screens at desktop and mobile widths, complete a demo, create a fictional account, test typed input, save/delete a session, and check microphone support if needed.
