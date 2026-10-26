# SQLite backup and restoration

The local demo uses SQLite. PostgreSQL production recovery requires its own operator-reviewed backup/restore process and is not verified by this tool.

No real user backup is made automatically. The commands below require explicit acknowledgement because account metadata and password hashes are sensitive even when transcript text is omitted. Store copies in a restricted, encrypted location; the SQLite file itself is **not encrypted**. Decide retention and who can access backups before operating on real accounts. Do not upload database files to chats, Git or the source ZIP.

## Create a metadata recovery copy

From the project directory, activate the installed Python environment. Create a private backup directory yourself, then run:

```powershell
python scripts/sqlite_recovery.py backup data/product.db private-backups/metadata.db --acknowledge-sensitive-data
```

Use a new destination filename each time. The tool refuses to overwrite existing files, reads the source through SQLite's backup API (including committed WAL content), checks integrity and foreign keys, removes login sessions, and excludes transcript/evidence text by default. It compacts the output so removed text is not left in free pages. The source database is unchanged. This recovers metadata and accounts, not a complete transcript history.

`--include-transcripts` is available only for an explicitly reviewed retention/privacy use case. Do not enable it casually. Any copy can outlive deletion from the live database; no immediate all-copies deletion guarantee is made. The tool never captures raw audio.

## Restore safely into a new file

Stop the application in its owning terminal before switching databases. Restore into a new path, never on top of a live database:

```powershell
python scripts/sqlite_recovery.py restore private-backups/metadata.db data/restored-product.db --acknowledge-sensitive-data
$env:DATABASE_URL = 'sqlite:///C:/absolute/path/to/catchy-ai/data/restored-product.db'
python -m backend.launcher --rules --no-browser
```

Replace the example absolute path with the restored file's actual location. The destination must not already exist and its parent must exist. Verify the printed health check, sign in again, and inspect expected history before deciding whether to keep using the restored copy. Old login sessions are not restored. Expired session rows are removed; formerly active sessions become interrupted and cannot resume processing. A new monitoring session requires explicit confirmation.

Transcripts remain excluded during restore unless the operator explicitly supplies `--include-transcripts` for a previously approved full-text backup. Restoring from a metadata-only copy cannot recover removed text.

Keep the prior database unchanged until validation is complete. Reverting DATABASE_URL after stopping the server switches back; it does not merge records created in the restored database. Do not run two instances against different copies and assume that their histories synchronize.

## Synthetic verification

`tests/test_recovery.py` exercises the real utility against temporary synthetic accounts and sessions. It checks metadata recovery via the application API, rejection of old cookies, login, interruption of old active sessions, deletion, absence of excluded transcript bytes, source preservation, optional transcript copy, expiry pruning, overwrite refusal and acknowledgement requirements. Test results belong in `docs/MASTER-PHASE-RESULTS.md`; having commands here alone is not proof of recoverability.

RPO/RTO, scheduling, encryption/key management, backup retention, external-provider copies and deletion-audit policy remain deployment decisions. This utility is a local recovery building block, not a complete production backup service.
