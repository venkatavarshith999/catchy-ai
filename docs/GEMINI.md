# Gemini setup

Run **START-GEMINI.bat**, paste your Gemini API key into the hidden terminal prompt and keep that window open. The key stays in the process environment; the launcher does not save it to a file. Keys shared in chat should be replaced through [Google AI Studio](https://aistudio.google.com/api-keys); enter replacements privately in the launcher.

For deployment, set `LLM_PROVIDER=gemini`, `GEMINI_API_KEY` and optionally `GEMINI_MODEL` (default `gemini-3.1-flash-lite`). Both Compose files pass these variables to the backend. Native Python reads environment variables, not `.env` automatically. Actual `.env` files are excluded from Git and the ZIP. Never add a secret to `.env.example` or frontend code.

The backend calls Google's HTTPS `generateContent` endpoint using the key in the `x-goog-api-key` header. It sends at most eight recent redacted text turns, capped at 1,500 characters each, with a JSON schema and 1,600 output-token limit. It sends no raw audio or tool requests. Redaction is best effort. Review [Google's terms](https://ai.google.dev/gemini-api/terms) for data handling appropriate to your account; no zero-retention promise is made.

Requests use a five-second HTTP phase timeout by default, configurable with `LLM_TIMEOUT` from 0.1 to 10 seconds. There are no automatic retries or automatic switches to a different paid provider. Auth/quota errors, unavailable models, safety blocks, incomplete output and invalid evidence retain rules-based detection. A low score is not proof that a caller is genuine.

`/api/health` reports `llm.provider=gemini` and whether a key is present, not verified connectivity. Analysis returns `model_status=connected` only after a valid response; otherwise `unavailable`. Tests use mocked keys and make no provider requests. Model availability, quota and usage charges depend on your Google project. n8n is not required.

Sources: [Gemini keys](https://ai.google.dev/gemini-api/docs/generate-content/api-key), [structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
