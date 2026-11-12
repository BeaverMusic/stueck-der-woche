#!/usr/bin/env python3
"""Baut alle Dateien einer Veröffentlichung in den Ordner dist/:

    stueck-der-woche-<Version>.zip   Programm (für Updates, Linux und install.sh)
    Stück der Woche <Version>.dmg    Mac-Installationsabbild
    SHA256SUMS.txt                   Prüfsummen (die Update-Funktion prüft damit)

Aufruf:  python3 paket/build_release.py
Auf GitHub erledigt das der Bauplan .github/workflows/release.yml automatisch.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import VERSION  # noqa: E402

# Was zur Programm-ZIP gehört (alles andere – Tests, .git, dist – bleibt draußen)
INCLUDE = ["app", "web", "paket", "stueck_der_woche.py", "install.sh", "deinstallieren.sh",
           "start.sh", "start.command", "LIESMICH.md", "README.md", "LICENSE"]
SKIP_PARTS = {"__pycache__", ".DS_Store", "src", "pkg"}
# Immer ausführbar – auch wenn die Rechte beim Hochladen über die GitHub-Webseite verloren gingen
EXECUTABLE = {"install.sh", "deinstallieren.sh", "start.sh", "start.command", "stueck_der_woche.py",
              "paket/mac/StueckDerWoche", "paket/build_release.py", "paket/mac/build_dmg.py"}


def build_zip(dist: Path) -> Path:
    out = dist / f"stueck-der-woche-{VERSION}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in INCLUDE:
            path = ROOT / name
            if not path.exists():
                continue
            files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
            for f in files:
                rel = f.relative_to(ROOT)
                if SKIP_PARTS & set(rel.parts) or f.suffix in (".pyc", ".dmg", ".zst"):
                    continue
                info = zipfile.ZipInfo(f"stueck-der-woche/{rel.as_posix()}", date_time=(2026, 1, 1, 0, 0, 0))
                exe = rel.as_posix() in EXECUTABLE or os.access(f, os.X_OK)
                info.external_attr = (0o755 if exe else 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, f.read_bytes())
    return out


def main() -> None:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    for old in dist.iterdir():
        old.unlink()
    files = [build_zip(dist)]
    subprocess.run([sys.executable, str(ROOT / "paket" / "mac" / "build_dmg.py"), str(dist)], check=True)
    files += sorted(dist.glob("*.dmg"))
    lines = [f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}" for f in files]
    (dist / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", "utf-8")
    for line in lines:
        print(line)
    print(f"Fertig: {dist}")


if __name__ == "__main__":
    main()
