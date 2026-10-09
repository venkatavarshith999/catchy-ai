"""Build a source ZIP excluding credentials, databases and caches."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
SKIP={'.git','__pycache__','.venv','node_modules','data','artifacts'}
def package(destination=None):
    destination=Path(destination) if destination else ROOT/'artifacts'/'catchy-ai.zip'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(ROOT)
            if any(part in SKIP for part in relative.parts):continue
            if path.name in {'.env','current-image'} or path.suffix in {'.pyc','.db','.zip'} or path.name.endswith(('.db-wal','.db-shm')):continue
            archive.write(path,Path('catchy-ai')/relative)
    print(destination)
if __name__=='__main__':package()
