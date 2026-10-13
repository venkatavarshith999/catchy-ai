# API v2

Development OpenAPI: `/api/docs` and `/api/openapi.json`. Disabled in production. `/` and `/dashboard` serve the responsive product UI. The v1 server is retained separately.

Mutations require `Origin: <APP_ORIGIN>` and `X-Catchy-Request: 1`; authenticated requests use the `catchy_v2` cookie. Never place session tokens in URLs. JSON request bodies are bounded to 100 KB. Validation errors omit submitted values.

| Method | Path under `/api/v2` | Purpose |
| --- | --- | --- |
| POST | `/auth/register`, `/auth/login` | Email/password account and session |
| POST | `/password/request`, `/password/confirm` | Expiring email-code recovery and session revocation |
| GET | `/me` | Current user and preferences |
| POST | `/logout` | Invalidate current session |
| POST | `/verify/request`, `/verify/confirm` | Verified email ownership, rate-limited expiring codes |
| POST | `/preferences` | Save a complete preferences object; omitted fields take defaults |
| POST | `/guest/analyze` | Consented temporary analysis, no history |
| GET/POST | `/calls` | Owned session list / create |
| GET/DELETE | `/calls/{id}` | Owned session detail / deletion |
| POST | `/calls/{id}/turns` | Text, request_id and optional timing |
| POST | `/calls/{id}/finish` | Stop and clear live context |
| WS | `/live/{id}` | Authenticated typed/speech text updates |
| WS | `/asr?language=hi-IN` | Bounded binary WebM relay to configured private ASR |
| GET/POST | `/contacts` | Outgoing/incoming relationships / create invitation |
| POST | `/contacts/accept` | Matching verified recipient accepts token and supplies own phone |
| POST | `/contacts/{id}/alerts` | Change the caller's side of mutual consent |
| POST | `/contacts/{id}/notify` | Explicit metadata-only alert or test |
| DELETE | `/contacts/{id}` | Owner or recipient revokes relationship |
| DELETE | `/account` | Remove account, SQL associations and active call memory |
| POST | `/analytics` | Consented, allowlisted anonymous event count |
| GET/POST | `/evaluation` | Verified administrator reads / runs synthetic report |

`/api/health` checks configured database/cache readiness. `/api/metrics` requires `Authorization: Bearer <METRICS_TOKEN>` and returns aggregate account/session counts.

Example guest request:

```json
{"turns":["Read your OTP to me"],"language":"en","consent":true}
```

Risk results contain `level`, explainable signals, model status and text-engine timing. This timing excludes speech recognition. `alert_new` gates repeated alerts for signed-in sessions. Call details contain empty transcript/evidence arrays when retention is off.

## Alert provider contract

When `ALERT_WEBHOOK_URL` is configured it must be HTTPS. The POST carries `Authorization: Bearer <ALERT_WEBHOOK_TOKEN>` and the routing/incident object implemented in `backend/notifications.py`. Incident fields are **risk, time and language only**. Recipient address is separately required for delivery. No call ID, speaker content, transcript or audio is sent. Return a 2xx status only after accepting the request. Provider acceptance is not delivery confirmation; no automatic retry occurs after uncertain delivery.

Invitation links are copied and shared by the user. The app does not automatically send invitations. A recipient's phone number is self-asserted during verified-email acceptance, not independently SMS-verified.
