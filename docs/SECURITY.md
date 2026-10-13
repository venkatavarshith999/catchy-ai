# Security and privacy implementation

Session cookies are HttpOnly and SameSite=Strict, with Secure enabled on HTTPS. Stored session tokens and verification codes are hashed; passwords use salted PBKDF2 from the preserved authentication utility. Ownership is checked for sessions and relationships. Administrator assignment uses an environment allowlist and evaluation access also requires verified email.

Mutation origin checks, a required custom request header, bounded input, parameterized SQLAlchemy operations, CSP and a frontend-only static route constrain common attack paths. Public caching excludes APIs. WebSocket messages recheck authentication, limits and context expiry. Redis locks serialize call updates and alert cooldowns.

The application does not save raw audio. Submitted conversation text is redacted before retention and model requests. Redaction is best effort, not a guarantee of anonymity. Transcripts/evidence are opt-in per new call. Browser/Android speech services have their own processing policies. The optional self-hosted worker processes audio in memory, but infrastructure must also avoid recording request streams, process dumps or sensitive traces.

Contacts must accept using the invited verified email. Alert delivery requires acceptance, both consent flags, the sender's setting, explicit request and high-risk call state (or an explicit test). Revocation blocks later requests. Metadata has only risk/time/language; provider routing separately requires an address. Recipient phone numbers are self-asserted, not SMS-verified.

Account deletion removes owned and recipient contact relationships, logins, sessions and delivery rows through foreign-key cascades, and clears owned live context. Configure backup expiration separately. Current initial-schema management does not replace a future migration system. This release has no independent penetration test, formal accessibility certification or external privacy/legal sign-off.

Dependency scanning is included in CI. Secrets are environment variables. The packager excludes `.env` files, database files, caches, signing keys and runtime data, and includes only named synthetic fixtures under `data/`. Keep infrastructure logs and monitoring free of request content; the optional monitoring hook receives only fixed event metadata.

Password recovery uses emailed, hashed six-digit codes with a 10-minute lifetime, at most five guesses, per-email/per-address request limits and single-use confirmation. Codes are tied to the account ID and its current password hash. Response bodies have the same shape for unknown accounts. On success all login sessions are revoked, active calls finish, and their live context is removed. SMTP is required outside explicit development-code mode. Request timing is not claimed to be indistinguishable across accounts.
