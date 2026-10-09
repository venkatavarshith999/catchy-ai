# Database guide

SQLite initializes automatically from 001_initial.sql. Foreign keys, WAL journaling and parameterized queries are enabled. No database binary or user records are included in the archive.

- users: identity and salted password hash.
- auth_sessions: hashed opaque token and eight-hour expiry.
- calls: owner, title, mode, score, lifecycle, retention snapshot and turn count.
- turns: optional redacted transcript and evidence, ordered within a call.
- contacts: private contact name, number and relationship.
- settings: retention and spoken-warning preferences.

Deleting a call cascades to its turns. Every session lookup includes the owner's account ID. Contact operations are owner-scoped. The initial schema is for fresh installations; future changes need a migration runner and compatibility strategy.

Use SQLite's online backup API for a running database. Do not copy only the main database file while WAL writes are active. Keep encrypted, access-restricted backups and test restoring into a separate environment. Deleted records can remain in older backups until operator-defined retention expires.
