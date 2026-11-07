"""Cook every species at several bloom values and report size, time and errors.

usage: hython tests/smoke_cook.py [path/to/hda]
"""
import json
import pathlib
import sys
import time

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
hda = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else next((ROOT / "otls").glob("ksd_flower_generator.hda*"))
hou.hda.installFile(hda.as_posix())

species = [k for k in json.loads((ROOT / "presets" / "species.json").read_text()) if not k.startswith("_")]
geo = hou.node("/obj").createNode("geo", "smoke")
node = geo.createNode("ksd::flower_generator::1.0")

def menu_conditional_problems(ptg):
    """Menu parms compare by token in conditionals; a bare integer term needs a token term beside it."""
    import re
    flat = []

    def walk(items):
        for t in items:
            flat.append(t)
            if isinstance(t, hou.FolderParmTemplate):
                walk(t.parmTemplates())
    walk(ptg.entries())
    menus = [t.name() for t in flat if t.type() == hou.parmTemplateType.Menu]
    bad = []
    for t in flat:
        for c in t.conditionals().values():
            for group in re.findall(r"\{([^}]*)\}", c):
                for m in menus:
                    terms = re.findall(m + r"\s*(?:!=|==)\s*(\S+)", group)
                    if any(x.isdigit() for x in terms) and not any(not x.isdigit() for x in terms):
                        bad.append((t.name(), c))
    return bad


failed = 0
for name, c in menu_conditional_problems(node.parmTemplateGroup()):
    failed += 1
    print(f"FAIL conditional on a menu parm uses a bare integer: {name}: {c}")
for sp in species:
    node.parm("species").set(sp)
    node.hdaModule().apply_species(node)
    for b in (0.0, 0.5, 1.0):
        node.parm("bloom").set(b)
        t0 = time.perf_counter()
        try:
            g = node.geometry()
            errs = node.errors()
        except hou.OperationFailed as e:
            g, errs = None, [str(e)]
        ms = (time.perf_counter() - t0) * 1000
        if errs or g is None:
            failed += 1
            print(f"FAIL {sp} bloom={b}: {errs}")
            continue
        bb = g.boundingBox()
        print(f"ok   {sp:8s} bloom={b:.1f} pts={len(g.points()):6d} prims={len(g.prims()):6d} "
              f"size={bb.sizevec()[0]:.3f}x{bb.sizevec()[1]:.3f}x{bb.sizevec()[2]:.3f} {ms:6.1f} ms")
print("FAILED" if failed else "ALL OK", failed)
sys.exit(1 if failed else 0)
