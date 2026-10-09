import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def connect():
    path = Path(os.environ.get('DATABASE_PATH', str(ROOT / 'data' / 'catchy.db')))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA journal_mode=WAL')
    return connection

def initialize():
    connection = connect()
    try:
        connection.executescript((ROOT / 'database' / '001_initial.sql').read_text())
        connection.commit()
    finally:
        connection.close()
