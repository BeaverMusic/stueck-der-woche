#!/usr/bin/env python3
"""Baut das Mac-Installationsabbild „Stück der Woche.dmg“.

    python3 paket/mac/build_dmg.py  [Zielordner]

Inhalt des Abbilds:
    Stück der Woche.app   – vollständige App (Programm, Symbol, Startprogramm)
    Programme             – Verknüpfung zum Ordner /Applications (zum Hineinziehen)
    Erste Schritte.txt    – kurze Anleitung

Auf einem Mac wird das Abbild mit hdiutil erzeugt (komprimiert, HFS+). Auf anderen
Systemen schreibt das Skript selbst ein ISO-9660-Abbild mit Rock-Ridge-Erweiterungen
(Dateirechte, lange Namen, Verknüpfungen), das macOS ebenso per Doppelklick öffnet.
"""

from __future__ import annotations

import io
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
APP_NAME = "Stück der Woche"
VOLUME = "Stück der Woche"

sys.path.insert(0, str(ROOT))
from app import VERSION  # noqa: E402

GUIDE = f"""Stück der Woche {VERSION} – Installation
==========================================

1. Doppelklick auf „Stück der Woche“.
   Die App kopiert sich selbst in den Ordner „Programme“.
   (Oder: die App auf „Programme“ ziehen.)

2. Meldet macOS beim ersten Öffnen, die App könne nicht überprüft werden:
   „Fertig“ klicken, dann Systemeinstellungen → Datenschutz & Sicherheit,
   ganz nach unten scrollen und bei „Stück der Woche“ auf „Dennoch öffnen“
   klicken. Das ist nur einmal nötig. (Grund: Die App ist nicht bei Apple
   registriert – das kostet Entwickler:innen eine Jahresgebühr.)

3. Fehlt Python, bietet die App an, es zu installieren (kostenlos, von
   python.org; macOS fragt dafür nach deinem Passwort).

Danach startet die App über Spotlight: Cmd+Leertaste, „Stück“ tippen, Enter.

Update: Neues Abbild öffnen und wieder Schritt 1 – Blätter, Einstellungen und
Schlüssel bleiben erhalten.
"""


# ---------------------------------------------------------------- App-Bundle

def make_icns(png: Path) -> bytes:
    """Mac-Symboldatei aus einem großen PNG (moderne icns-Typen mit PNG-Inhalt)."""
    from PIL import Image

    src = Image.open(png).convert("RGBA")
    types = [("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128), ("ic08", 256),
             ("ic09", 512), ("ic10", 1024), ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512)]
    chunks = b""
    for code, size in types:
        buf = io.BytesIO()
        src.resize((size, size), Image.LANCZOS).save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        chunks += code.encode() + struct.pack(">I", len(data) + 8) + data
    return b"icns" + struct.pack(">I", len(chunks) + 8) + chunks


def bundle_version(version: str) -> str:
    """Interne Versionsnummer für macOS: höchstens drei Zahlen, weiterhin aufsteigend
    (0.6 → 0.6, 0.6.0.1 → 0.6.1, 0.6.1 → 0.6.1000, 0.6.1.2 → 0.6.1002)."""
    import re
    nums = [int(x) for x in re.findall(r"\d+", version)] or [0]
    nums = (nums + [0, 0, 0, 0])[:4]
    return f"{nums[0]}.{nums[1]}.{nums[2] * 1000 + nums[3]}"


def build_app(target: Path) -> Path:
    app = target / f"{APP_NAME}.app"
    contents = app / "Contents"
    prog = contents / "Resources" / "programm"
    (contents / "MacOS").mkdir(parents=True)
    prog.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    shutil.copytree(ROOT / "app", prog / "app", ignore=ignore)
    shutil.copytree(ROOT / "web", prog / "web", ignore=ignore)
    for name in ("stueck_der_woche.py", "LIESMICH.md", "deinstallieren.sh", "LICENSE"):
        shutil.copy2(ROOT / name, prog / name)
    (prog / "deinstallieren.sh").chmod(0o755)
    launcher = contents / "MacOS" / "StueckDerWoche"
    shutil.copy2(HERE / "StueckDerWoche", launcher)
    launcher.chmod(0o755)
    (contents / "Resources" / "StueckDerWoche.icns").write_bytes(make_icns(ROOT / "app" / "icon.png"))
    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "de.musik.stueck-der-woche",
        "CFBundleExecutable": "StueckDerWoche",
        "CFBundleIconFile": "StueckDerWoche",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": bundle_version(VERSION),
        "CFBundleDevelopmentRegion": "de",
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.education",
        "LSUIElement": True,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    (contents / "PkgInfo").write_bytes(b"APPL????")
    return app


# ---------------------------------------------------------------- ISO 9660 + Rock Ridge

SECTOR = 2048


def both16(n: int) -> bytes:
    return struct.pack("<H", n) + struct.pack(">H", n)


def both32(n: int) -> bytes:
    return struct.pack("<I", n) + struct.pack(">I", n)


def dir_date(t: float) -> bytes:
    g = time.gmtime(t)
    return bytes([g.tm_year - 1900, g.tm_mon, g.tm_mday, g.tm_hour, g.tm_min, g.tm_sec, 0])


def vol_date(t: float) -> bytes:
    return time.strftime("%Y%m%d%H%M%S00", time.gmtime(t)).encode() + b"\x00"


class Node:
    def __init__(self, name: str, path: Path | None, kind: str, parent=None):
        self.name = unicodedata.normalize("NFD", name)  # Schreibweise, die macOS selbst nutzt
        self.path, self.kind, self.parent = path, kind, parent  # kind: dir | file | link
        self.children: list[Node] = []
        self.iso = b""
        self.lba = 0
        self.size = 0
        self.number = 0
        self.mode = 0
        self.target = ""
        self.mtime = time.time()


def rr_fields(node: Node, name: bool = True) -> bytes:
    nlink = 2 + sum(1 for c in node.children if c.kind == "dir") if node.kind == "dir" else 1
    px = b"PX" + bytes([36, 1]) + both32(node.mode) + both32(nlink) + both32(0) + both32(0)
    tf = b"TF" + bytes([19, 1, 0x06]) + dir_date(node.mtime) + dir_date(node.mtime)
    flags = 0x01 | 0x80  # PX, TF
    extra = b""
    if name:
        raw = node.name.encode("utf-8")
        extra += b"NM" + bytes([5 + len(raw), 1, 0]) + raw
        flags |= 0x08
    if node.kind == "link":
        comps = b""
        for i, part in enumerate(node.target.split("/")):
            if i == 0 and part == "":
                comps += bytes([0x08, 0])  # Wurzel „/“
            elif part:
                raw = part.encode("utf-8")
                comps += bytes([0, len(raw)]) + raw
        extra += b"SL" + bytes([5 + len(comps), 1, 0]) + comps
        flags |= 0x04
    rr = b"RR" + bytes([5, 1, flags])
    return rr + px + tf + extra


def record(iso_name: bytes, lba: int, size: int, is_dir: bool, mtime: float, su: bytes) -> bytes:
    pad = b"\x00" if len(iso_name) % 2 == 0 else b""
    body = (b"\x00" + both32(lba) + both32(size) + dir_date(mtime) + bytes([2 if is_dir else 0, 0, 0])
            + both16(1) + bytes([len(iso_name)]) + iso_name + pad + su)
    if (len(body) + 1) % 2:
        body += b"\x00"
    if len(body) + 1 > 255:
        raise ValueError(f"Name zu lang für das Abbild: {iso_name!r}")
    return bytes([len(body) + 1]) + body


def write_iso(src: Path, out: Path, volume: str) -> None:
    # Baum einlesen
    root = Node("", src, "dir")
    root.mode = 0o40755

    def scan(node: Node) -> None:
        for entry in sorted(node.path.iterdir(), key=lambda p: p.name):
            if entry.is_symlink():
                kid = Node(entry.name, entry, "link", node)
                kid.target = os.readlink(entry)
                kid.mode = 0o120755
            elif entry.is_dir():
                kid = Node(entry.name, entry, "dir", node)
                kid.mode = 0o40755
                scan(kid)
            else:
                kid = Node(entry.name, entry, "file", node)
                kid.size = entry.stat().st_size
                kid.mode = 0o100755 if os.access(entry, os.X_OK) else 0o100644
            kid.mtime = entry.lstat().st_mtime
            node.children.append(kid)
        # Kurze ISO-Namen (die eigentlichen Namen stehen in Rock Ridge „NM“)
        for i, kid in enumerate(node.children, 1):
            kid.iso = (f"D{i:05d}" if kid.kind == "dir" else f"F{i:05d}.;1").encode()

    scan(root)

    dirs: list[Node] = []  # Reihenfolge der Pfadtabelle: breitenweise
    queue = [root]
    while queue:
        d = queue.pop(0)
        dirs.append(d)
        d.number = len(dirs)
        queue.extend(c for c in d.children if c.kind == "dir")

    # Pfadtabelle
    def path_table(big: bool) -> bytes:
        out_ = b""
        for d in dirs:
            ident = b"\x00" if d is root else d.iso
            parent = 1 if d is root else d.parent.number
            out_ += bytes([len(ident), 0]) + struct.pack(">I" if big else "<I", d.lba) \
                + struct.pack(">H" if big else "<H", parent) + ident + (b"\x00" if len(ident) % 2 else b"")
        return out_

    # Fortsetzungsbereich (CE) für die Rock-Ridge-Kennung im Wurzelordner
    er_id, er_des = b"RRIP_1991A", b"THE ROCK RIDGE INTERCHANGE PROTOCOL PROVIDES SUPPORT FOR POSIX FILE SYSTEM SEMANTICS"
    er_src = b"PLEASE CONTACT DISC PUBLISHER FOR SPECIFICATION SOURCE.  SEE PUBLISHER IDENTIFIER IN PRIMARY VOLUME DESCRIPTOR FOR CONTACT INFORMATION."
    er = b"ER" + bytes([8 + len(er_id) + len(er_des) + len(er_src), 1, len(er_id), len(er_des), len(er_src), 1]) \
        + er_id + er_des + er_src

    def dir_records(d: Node, ce_lba: int) -> list[bytes]:
        recs = []
        if d is root:
            sp = b"SP" + bytes([7, 1, 0xBE, 0xEF, 0])
            ce = b"CE" + bytes([28, 1]) + both32(ce_lba) + both32(0) + both32(len(er))
            dot_su = sp + rr_fields(d, name=False) + ce
        else:
            dot_su = rr_fields(d, name=False)
        parent = d.parent or d
        recs.append(record(b"\x00", d.lba, d.size, True, d.mtime, dot_su))
        recs.append(record(b"\x01", parent.lba, parent.size, True, parent.mtime, rr_fields(parent, name=False)))
        for c in d.children:
            recs.append(record(c.iso, c.lba, c.size, c.kind == "dir", c.mtime, rr_fields(c)))
        return recs

    def extent_size(recs: list[bytes]) -> int:
        used, sectors = 0, 1
        for r in recs:
            if used + len(r) > SECTOR:
                sectors += 1
                used = 0
            used += len(r)
        return sectors * SECTOR

    # Platz verteilen: 0–15 leer, 16 PVD, 17 Ende, dann Pfadtabellen, Ordner, CE, Dateien
    pt_size = len(path_table(False))
    pt_sectors = (pt_size + SECTOR - 1) // SECTOR
    lba = 18
    l_pt = lba
    lba += pt_sectors
    m_pt = lba
    lba += pt_sectors
    cur = lba
    for d in dirs:
        d.size = extent_size(dir_records(d, 0))  # Länge hängt nicht von den Positionen ab
        d.lba = cur
        cur += d.size // SECTOR
    ce_lba = cur  # hinter den Ordnern – manche Leseprogramme lesen streng der Reihe nach
    cur += 1
    files = []

    def collect(d: Node) -> None:
        for c in d.children:
            if c.kind == "file":
                files.append(c)
            elif c.kind == "dir":
                collect(c)

    collect(root)
    for f in files:
        f.lba = cur if f.size else 0
        cur += (f.size + SECTOR - 1) // SECTOR
    total = cur

    # Schreiben
    with open(out, "wb") as fh:
        def at(sector: int, data: bytes) -> None:
            fh.seek(sector * SECTOR)
            fh.write(data)

        now = time.time()
        label = "".join(c if c.isalnum() else "_" for c in
                        volume.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe").upper().encode("ascii", "ignore").decode())[:32]
        root_rec = record(b"\x00", root.lba, root.size, True, root.mtime, b"")
        pvd = (b"\x01CD001\x01\x00" + b" " * 32 + label.ljust(32).encode() + b"\x00" * 8 + both32(total)
               + b"\x00" * 32 + both16(1) + both16(1) + both16(SECTOR) + both32(pt_size)
               + struct.pack("<I", l_pt) + b"\x00" * 4 + struct.pack(">I", m_pt) + b"\x00" * 4
               + root_rec + b" " * 128 + b" " * 128 + b" " * 128
               + b"STUECK DER WOCHE INSTALLER".ljust(128) + b" " * 37 * 3
               + vol_date(now) + vol_date(now) + b"0" * 16 + b"\x00" + vol_date(now) + b"\x01\x00")
        at(16, pvd.ljust(SECTOR, b"\x00"))
        at(17, b"\xffCD001\x01".ljust(SECTOR, b"\x00"))
        at(l_pt, path_table(False))
        at(m_pt, path_table(True))
        at(ce_lba, er)
        for d in dirs:
            buf, used = b"", 0
            for r in dir_records(d, ce_lba):
                if used + len(r) > SECTOR:
                    buf += b"\x00" * (SECTOR - used)
                    used = 0
                buf += r
                used += len(r)
            at(d.lba, buf.ljust(d.size, b"\x00"))
        for f in files:
            if f.size:
                at(f.lba, f.path.read_bytes())
        fh.truncate(total * SECTOR)


# ---------------------------------------------------------------- Hauptteil

def main() -> None:
    out_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT.parent
    out = out_dir / f"Stueck-der-Woche-{VERSION}.dmg"  # ohne Umlaut/Leerzeichen (GitHub ändert sie sonst)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "inhalt"
        stage.mkdir()
        build_app(stage)
        os.symlink("/Applications", stage / "Programme")
        (stage / "Erste Schritte.txt").write_text(GUIDE, "utf-8")
        if out.exists():
            out.unlink()
        if shutil.which("hdiutil"):
            subprocess.run(["hdiutil", "create", "-volname", VOLUME, "-srcfolder", str(stage),
                            "-fs", "HFS+", "-format", "UDZO", "-ov", str(out)], check=True)
        else:
            write_iso(stage, out, VOLUME)
    print(f"Fertig: {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
