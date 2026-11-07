"""Count real surface crossings in the flower head across the bloom.

usage: hython tests/intersection_test.py [steps (default 40 = 41 stages)] [max_allowed] [species,...]

For every species and bloom value it runs Houdini's Intersection Analysis on the
head (in head space, after the de-intersect pass) and counts intersection points
between two differently named parts where at least one is a petal or sepal,
ignoring the attachment zone at the blade bases (blade_s < 0.15), which sits in
the receptacle by design. Each value is measured with the pass off and on.
Fails when any frame with the pass on has more than max_allowed crossing points
(default 0).

Intersection Analysis's "sourceprim" pair does not reliably name the two
primitives, so both surfaces are found again by position: the nearest primitive,
and the nearest primitive with a different name; both must pass through the hit.
"""
import json
import os
import pathlib
import sys
import time

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
steps = int(sys.argv[1]) if len(sys.argv) > 1 else 40
allowed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())

species = [k for k in json.loads((ROOT / "presets" / "species.json").read_text()) if not k.startswith("_")]
if len(sys.argv) > 3:
    species = sys.argv[3].split(",")
geo = hou.node("/obj").createNode("geo", "isect")
node = geo.createNode("ksd::flower_generator::1.0")
merge = geo.createNode("object_merge")
merge.parm("objpath1").set(node.path() + "/deintersect_clean")
tris = geo.createNode("divide")
tris.setInput(0, merge)
tris.parm("numsides").set(3)
ia = geo.createNode("intersectionanalysis")
ia.setInput(0, tris)
ia.parm("useproxtol").set(0)
classify = geo.createNode("attribwrangle")
classify.setInput(0, ia)
classify.setInput(1, tris)
classify.parm("class").set("point")
classify.parm("snippet").set((ROOT / "tests" / "crossings.vfl").read_text())



def crossings():
    g = classify.geometry()
    if g is None:
        raise RuntimeError(classify.errors())
    a = g.findPointAttrib("crossing")
    return sum(g.pointIntAttribValues("crossing")) if a else 0


def breakdown():
    import collections
    g = classify.geometry()
    return dict(collections.Counter(p.attribValue("pair") for p in g.iterPoints() if p.attribValue("crossing")))


worst = 0
for sp in species:
    node.parm("species").set(sp)
    node.hdaModule().apply_species(node)
    if os.environ.get("FG_STEPS"):  # optional: Smooth Animation key count to test
        node.parm("smooth_steps").set(int(os.environ["FG_STEPS"]))
    if os.environ.get("FG_END"):  # optional: Viewpoint Settles At
        node.parm("deintersect_center_end").set(float(os.environ["FG_END"]))
    if os.environ.get("FG_SMOOTH"):  # optional: 0 or 1 for the Smooth Animation toggle
        node.parm("smooth_anim").set(int(os.environ["FG_SMOOTH"]))
    for kv in filter(None, os.environ.get("FG_SET", "").split(",")):  # optional: parm=value overrides
        k, v = kv.split("=")
        node.parm(k).set(float(v))
    off_counts, on_counts, ms = [], [], []
    for i in range(steps + 1):
        node.parm("bloom").set(i / steps)
        node.parm("deintersect").set(0)
        off_counts.append(crossings())
        node.parm("deintersect").set(1)
        t0 = time.perf_counter()
        node.geometry()
        ms.append((time.perf_counter() - t0) * 1000)
        on_counts.append(crossings())
    worst = max(worst, max(on_counts))
    if "-v" in sys.argv[4:]:
        print(f"{'':8s} last frame by part pair: {breakdown()}")
    print(f"{sp:8s} off {off_counts}")
    print(f"{'':8s} on  {on_counts}  cook {sum(ms) / len(ms):.0f} ms avg, {max(ms):.0f} ms max")
print("PASS" if worst <= allowed else "FAIL", "worst", worst)
sys.exit(0 if worst <= allowed else 1)
