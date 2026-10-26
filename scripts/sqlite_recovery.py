"""Explicit, new-file-only SQLite recovery; never run automatically on user data."""

import argparse
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def copy_database(source, destination, *, restore=False, include_transcripts=False):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(
            "Destination must be a new file; live databases are never overwritten"
        )
    if not destination.parent.is_dir():
        raise ValueError("Destination directory must already exist")
    created = False
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            tables = {
                row[0]
                for row in original.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not {"product_users", "product_calls", "product_logins"}.issubset(tables):
                raise ValueError("Source is not a supported Catchy product database")
            if original.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Source database integrity check failed")
            with destination.open("xb"):
                created = True
            with closing(sqlite3.connect(destination)) as copied:
                original.backup(copied)
                copied.execute("PRAGMA journal_mode=DELETE")
                copied.execute("PRAGMA foreign_keys=ON")
                copied.execute("PRAGMA secure_delete=ON")
                # Restoring a snapshot must never resurrect authenticated sessions.
                copied.execute("DELETE FROM product_logins")
                if not include_transcripts:
                    copied.execute(
                        "UPDATE product_calls SET transcript='[]', evidence='[]', retain=0"
                    )
                if restore:
                    copied.execute("DELETE FROM product_calls WHERE expires <= ?", (time.time(),))
                    copied.execute(
                        "UPDATE product_calls SET status='interrupted' WHERE status='active'"
                    )
                copied.commit()
                copied.execute("VACUUM")
                if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Copied database integrity check failed")
                if copied.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Copied database foreign-key check failed")
        return destination
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--include-transcripts",
        action="store_true",
        help="Requires an approved retention/privacy policy; default excludes transcripts",
    )
    parser.add_argument(
        "--acknowledge-sensitive-data",
        action="store_true",
        help="Acknowledge that account metadata and password hashes remain sensitive",
    )
    args = parser.parse_args(argv)
    if not args.acknowledge_sensitive_data:
        parser.error("Explicit --acknowledge-sensitive-data is required; no copy was created")
    copy_database(
        args.source,
        args.destination,
        restore=args.action == "restore",
        include_transcripts=args.include_transcripts,
    )
    print(
        "New SQLite copy verified. Login sessions removed. Protect this sensitive file; it is not encrypted."
    )
    if not args.include_transcripts:
        print(
            "Transcript and evidence text excluded. This is a metadata recovery copy, not a complete transcript backup."
        )
    if args.action == "restore":
        print(
            "Expired sessions removed; active sessions marked interrupted. Sign in again and explicitly start new monitoring."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
