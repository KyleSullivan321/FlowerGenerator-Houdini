#!/usr/bin/env python3
"""Build dist/FlowerGenerator-Houdini-<version>.zip, the install bundle for artists.

Usage: python tools/package.py
The zip holds what is needed to install and use the node: the package json (placeholder path), otls/ (the
node; its Python module is embedded, so nothing from python/ is needed at runtime), README.md, LICENSE and
docs/help.txt (the demo video stays out; the README links the GitHub copy). It also holds the build source (python/, vex/, presets/), so a
Houdini FX or Core user can build a commercial .hda with `hython python/build_hda.py` without the repo.
Tests and tools stay in the repo export.
Every file in the zip is re-scanned for private strings, the .hdalc through hython (CPU). Exit 1 on any hit.
"""
import pathlib
import sys
import tempfile
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import export_public as ep  # noqa: E402

VERSION = "0.1.0"
NAME = "FlowerGenerator-Houdini"
SHIP = ["houdini_flower_generator.json", "README.md", "LICENSE", "docs/help.txt"]
SHIP_PREFIX = ["otls/", "python/", "vex/", "presets/"]   # node + build source (no docs/media)


def main():
    dist = ep.ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / ("%s-%s.zip" % (NAME, VERSION))
    with tempfile.TemporaryDirectory() as tmp:  # outside the repo
        export_dir = pathlib.Path(tmp) / "export"
        code = ep.export(export_dir)
        if code:
            return code
        files = []
        for p in sorted(export_dir.rglob("*")):
            rel = p.relative_to(export_dir).as_posix()
            if p.is_file() and (rel in SHIP or any(rel.startswith(x) for x in SHIP_PREFIX)):
                files.append((p, rel))
        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p, rel in files:
                z.write(p, "%s-%s/%s" % (NAME, VERSION, rel))
    # Re-scan the finished zip itself, not the folder it came from.
    hits, hdalcs = [], {}
    with tempfile.TemporaryDirectory() as chk, zipfile.ZipFile(out) as z:
        for info in z.infolist():
            data = z.read(info)
            label = info.filename
            if label.endswith(".hdalc"):
                dst = pathlib.Path(chk) / pathlib.Path(label).name
                dst.write_bytes(data)
                hdalcs[label] = dst
            elif not label.endswith(ep.BINARY_SUFFIXES):
                hits += ep.scan_file_bytes(label, data)
        hits += ep.scan_hdalc(hdalcs)
    print("Zip: %s" % out)
    with zipfile.ZipFile(out) as z:
        for i in z.infolist():
            print("  %9d  %s" % (i.file_size, i.filename))
    print("  zip size: %d bytes" % out.stat().st_size)
    if hits:
        print("SCAN HITS (%d):" % len(hits))
        print("\n".join("  " + h for h in hits))
        return 1
    print("Zip scan clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
