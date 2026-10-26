"""Offline check used by the Windows launcher before installing dependencies."""

import importlib
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def main():
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required.")
        return 1
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    for line in requirements.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parsed = re.fullmatch(r"([A-Za-z0-9_-]+)(?:\[[^]]+\])?==([^ ;]+)", line.strip())
        if not parsed:
            print("Requirements changed; dependency installation is required.")
            return 1
        name, expected = parsed.groups()
        try:
            if version(name) != expected:
                print(f"Dependency update required: {name}")
                return 1
        except PackageNotFoundError:
            print(f"Missing dependency: {name}")
            return 1
    for module in (
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg",
        "redis",
        "httpx",
        "yaml",
        "multipart",
        "websockets",
        "httptools",
        "dotenv",
        "watchfiles",
    ):
        try:
            importlib.import_module(module)
        except (ImportError, OSError):
            print(f"Dependency repair required: {module}")
            return 1
    print("Installed runtime is ready; no download needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
