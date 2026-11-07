"""Crossing counts (de-intersect on) for one species while sweeping one parameter.

usage: hython tests/sweep.py species parm v1,v2,... [blooms b1,b2,...] [parm2=value ...]
"""
import pathlib
import sys

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.argv += [""] * 3
sp, parm, values = sys.argv[1], sys.argv[2], [float(v) for v in sys.argv[3].split(",")]
blooms = [float(b) for b in sys.argv[4].split(",")] if sys.argv[4] else [0, 0.25, 0.5, 0.75, 1]
fixed = [a.split("=") for a in sys.argv[5:] if "=" in a]
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())
geo = hou.node("/obj").createNode("geo", "sweep")
node = geo.createNode("ksd::flower_generator::1.0")
node.parm("species").set(sp)
node.hdaModule().apply_species(node)
for k, v in fixed:
    node.parm(k).set(float(v))
merge = geo.createNode("object_merge")
merge.parm("objpath1").set(node.path() + "/deintersect_clean")
tris = geo.createNode("divide")
tris.setInput(0, merge)
tris.parm("numsides").set(3)
ia = geo.createNode("intersectionanalysis")
ia.setInput(0, tris)
ia.parm("useproxtol").set(0)
cl = geo.createNode("attribwrangle")
cl.setInput(0, ia)
cl.setInput(1, tris)
cl.parm("class").set("point")
cl.parm("snippet").set((ROOT / "tests" / "crossings.vfl").read_text())
for v in values:
    node.parm(parm).set(v)
    out = []
    for b in blooms:
        node.parm("bloom").set(b)
        g = cl.geometry()
        out.append(sum(g.pointIntAttribValues("crossing")) if g.findPointAttrib("crossing") else 0)
    print(f"{sp} {parm}={v:g}: {out} sum {sum(out)}", flush=True)
