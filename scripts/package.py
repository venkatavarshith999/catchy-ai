"""Build a portable source archive; include synthetic fixtures, exclude user data."""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    "artifacts",
    ".pytest_cache",
    ".ruff_cache",
    ".gradle",
    "build",
    ".idea",
    ".build-temp",
}


def included(relative):
    if any(part in SKIP for part in relative.parts):
        return False
    if relative.parts[:2] == ("mobile", "web"):
        return False
    if relative.parts[:6] == ("android", "app", "src", "main", "assets", "public"):
        return False
    if relative.parts[:2] == ("android", "capacitor-cordova-android-plugins"):
        return False
    if (
        relative.name in {"capacitor.plugins.json", "capacitor.config.json"}
        and relative.parts[0] == "android"
    ):
        return False
    if relative.parts[0] == "data":
        return len(relative.parts) == 3 and relative.name == "cases.json"
    if relative.name.startswith(".env") and relative.name != ".env.example":
        return False
    if (
        relative.name in {"current-image", "local.properties"}
        or relative.suffix in {".pyc", ".db", ".zip", ".jks", ".keystore", ".apk", ".aab"}
        or relative.name.endswith((".db-wal", ".db-shm"))
    ):
        return False
    return True


def package(destination=None):
    destination = Path(destination) if destination else ROOT / "artifacts" / "catchy-ai.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if path.is_file() and not path.is_symlink() and included(relative):
                archive.write(path, Path("catchy-ai") / relative)
                count += 1
    print(f"{destination} ({count} files)")
    return destination


if __name__ == "__main__":
    package(sys.argv[1] if len(sys.argv) > 1 else None)
