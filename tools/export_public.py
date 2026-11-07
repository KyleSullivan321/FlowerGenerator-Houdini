#!/usr/bin/env python3
"""Export the public allowlist of this repo into an EMPTY folder outside the repo, then scan the copy.

Usage: python tools/export_public.py <empty target folder>
Exit codes: 0 clean, 1 private-string hits, 2 bad target or setup problem.

Only files that git tracks are considered (git ls-files), so untracked scratch files never leak.
The allowlist, with the reason for each entry:
  README.md, LICENSE            the public face and the licence
  houdini_flower_generator.json package file; written fresh with a placeholder path, never copied
  otls/*.hdalc                  the node itself (Indie file; scanned section by section through hython)
  python/                       build_hda.py and flowergen/: the source the node is built from
  vex/                          the VEX source of every wrangle, inlined at build time
  presets/                      species presets (also embedded in the node; the build reads this file)
  docs/help.txt                 node help text
  docs/media/                   demo poster and video, if present
  tests/                        headless checks a user needs to verify a rebuild
  tools/                        render_preview, render_bloom, contact_sheet, presets_edit, make_demo, make_example,
                                debug_crossings, and these export/package scripts
Left out: .agent/, CLAUDE.md, renders/ (dev test renders), examples/backup, examples/cache, examples/demo,
otls/backup, .gitignore, .gitattributes, and examples/flower_generator_demo.hiplc (made by tools/make_example.py,
but the saved scene embeds the author's absolute paths, so users regenerate it with that script).
The built node needs nothing from python/ at runtime: the PythonModule section is embedded in the HDA.
"""
import fnmatch
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

ALLOW = ["README.md", "LICENSE", "otls/*.hdalc", "python/*", "vex/*", "presets/*", "docs/help.txt",
         "docs/media/*", "tests/*", "tools/*"]
SANITIZED_JSON = {"env": [{"FLOWERGEN": "C:/path/to/FlowerGenerator-Houdini"}],
                  "path": "$FLOWERGEN", "load_package_once": True}

# Plain substrings, matched case-sensitively. The regexes cover tokens; "claude" is matched in any case because
# no public file has a reason to name the assistant. Token regexes are anchored so that words such as "task-list"
# do not trip them.
FORBIDDEN = ["C:\\Users\\Kyle", "C:/Users/Kyle", "C:\\General", "C:/General", "Claude Code Projects", ".agent",
             "HANDOFF", "CLAUDE.md", "Creative-Brain", "vram.py", "kylesullivandesign@gmail.com"]
FORBIDDEN_RE = [r"(?i)claude", r"ghp_[A-Za-z0-9]{10,}", r"gho_[A-Za-z0-9]{10,}", r"\bsk-[A-Za-z0-9_-]{16,}",
                r"\bxox[abprs]-[A-Za-z0-9-]{8,}", r"Co-Authored-By"]
# These two files list the strings, so they are exempt from the text scan.
SELF_EXEMPT = {"tools/export_public.py", "tools/package.py"}
BINARY_SUFFIXES = (".png", ".jpg", ".mp4")

HYTHON_DEFAULT = "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe"
HYTHON_SCANNER = """
import sys, json, hou
paths = json.loads(sys.argv[1]); out = {}
for p in paths:
    texts = []
    for d in hou.hda.definitionsInFile(p):
        for name, sec in d.sections().items():
            texts.append((d.nodeTypeName() + ":" + name, sec.contents()))
        texts.append((d.nodeTypeName() + ":<definition>", d.comment() + d.description() + d.version()))
    out[p] = texts
print("@@SCAN@@" + json.dumps(out))
"""


def scan_text(label, text):
    hits = ["%s: contains %r" % (label, s) for s in FORBIDDEN if s in text]
    for pat in FORBIDDEN_RE:
        m = re.search(pat, text)
        if m:
            hits.append("%s: matches %s (%r)" % (label, pat, m.group(0)))
    return hits


def scan_file_bytes(label, data):
    """Scan any file as latin-1 text. Fine for text and for uncompressed binaries such as .hiplc."""
    return scan_text(label, data.decode("latin-1"))


def scan_hdalc(paths):
    """Scan the sections of each .hdalc through hython (CPU only). paths: {label: real path}. Returns hits."""
    if not paths:
        return []
    hython = os.environ.get("HYTHON", HYTHON_DEFAULT)
    if not pathlib.Path(hython).exists():
        raise SystemExit("hython not found at %s (set HYTHON); cannot scan the .hdalc" % hython)
    env = dict(os.environ, HOUDINI_OCL_DEVICETYPE="CPU")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(HYTHON_SCANNER)
    try:
        r = subprocess.run([hython, f.name, json.dumps([str(p) for p in paths.values()])],
                           capture_output=True, text=True, env=env)
    finally:
        os.unlink(f.name)
    marker = [ln for ln in r.stdout.splitlines() if ln.startswith("@@SCAN@@")]
    if r.returncode or not marker:
        raise SystemExit("hython scan failed:\n" + r.stdout[-800:] + r.stderr[-800:])
    data = json.loads(marker[0][len("@@SCAN@@"):])
    hits, nsec = [], 0
    for label, real in paths.items():
        for name, text in data[str(real)]:
            nsec += 1
            hits += scan_text("%s [%s]" % (label, name), text)
    print("hdalc scan: %d file(s), %d sections/definitions checked" % (len(paths), nsec))
    return hits


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln]


def allowlisted(files):
    return [f for f in files if f != "houdini_flower_generator.json"
            and any(fnmatch.fnmatch(f, pat) for pat in ALLOW)]


def scan_tree(base):
    """Scan every file under `base`. Returns hits."""
    hits, hdalcs = [], {}
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(base).as_posix()
        if p.suffix == ".hdalc":
            hdalcs[rel] = p
        elif rel not in SELF_EXEMPT and p.suffix not in BINARY_SUFFIXES:
            hits += scan_file_bytes(rel, p.read_bytes())
    return hits + scan_hdalc(hdalcs)


def export(target):
    target = pathlib.Path(target).resolve()
    if ROOT == target or ROOT in target.parents:
        print("Refusing: the target must be outside the repo.")
        return 2
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        print("Refusing: %s exists and is not an empty folder." % target)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    files = allowlisted(tracked_files())
    for rel in files:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / rel).read_bytes())
    (target / "houdini_flower_generator.json").write_text(json.dumps(SANITIZED_JSON, indent=4) + "\n")
    print("Exported %d files to %s" % (len(files) + 1, target))
    for p in sorted(target.rglob("*")):
        if p.is_file():
            print("  %9d  %s" % (p.stat().st_size, p.relative_to(target).as_posix()))
    return 0


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    code = export(argv[1])
    if code:
        return code
    hits = scan_tree(pathlib.Path(argv[1]).resolve())
    if hits:
        print("SCAN HITS (%d):" % len(hits))
        print("\n".join("  " + h for h in hits))
        return 1
    print("Scan clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
