"""Which parts cross, for one species and bloom value.

usage: hython tests/crossing_pairs.py species bloom [deintersect 0|1] [top N] [parm=value ...]

Prints crossing points by part pair and the petal or sepal pairs (by name) with
the most crossings, with each petal's order, so a bad layer is easy to find.
"""
import collections
import pathlib
import sys

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
sp, bloom = sys.argv[1], float(sys.argv[2])
on = int(sys.argv[3]) if len(sys.argv) > 3 else 1
top = int(sys.argv[4]) if len(sys.argv) > 4 else 12
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())

geo = hou.node("/obj").createNode("geo", "pairs")
node = geo.createNode("ksd::flower_generator::1.0")
node.parm("species").set(sp)
node.hdaModule().apply_species(node)
node.parm("bloom").set(bloom)
node.parm("deintersect").set(on)
import os
if os.environ.get("ROWS"): node.parm("petal_rows").set(int(os.environ["ROWS"]))
if os.environ.get("COLS"): node.parm("petal_cols").set(int(os.environ["COLS"]))
for k, v in (a.split("=") for a in sys.argv[5:] if "=" in a):
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
cl.parm("snippet").set((ROOT / "tests" / "crossings.vfl").read_text() + """
if (i@crossing) {
    int qa, qb; vector uu;
    xyzdist(1, "", v@P, qa, uu);
    string a = prim(1, "name", qa);
    xyzdist(1, "* ^@name=" + a, v@P, qb, uu);
    string b = prim(1, "name", qb);
    s@names = a < b ? a + " " + b : b + " " + a;
    f@height = v@P.y;
    f@rad = length(set(v@P.x, 0, v@P.z));
}
""")
g = cl.geometry()
parts, names = collections.Counter(), collections.Counter()
hs = collections.defaultdict(list)
for p in g.iterPoints():
    if p.attribValue("crossing"):
        parts[p.attribValue("pair")] += 1
        n = p.attribValue("names")
        names[n] += 1
        hs[n].append((p.attribValue("height"), p.attribValue("rad")))
print(sp, "bloom", bloom, "deintersect", on, "total", sum(parts.values()), dict(parts))
for n, c in names.most_common(top):
    h = sorted(x[0] for x in hs[n])
    r = sorted(x[1] for x in hs[n])
    print(f"  {n:24s} {c:5d}  y {h[0]*1000:6.1f}..{h[-1]*1000:6.1f} mm  r {r[0]*1000:5.1f}..{r[-1]*1000:5.1f} mm")
