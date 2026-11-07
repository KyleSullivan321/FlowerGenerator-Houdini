"""Cook time of every node inside the HDA, slowest first.

usage: hython tests/node_times.py [species] [bloom]
"""
import pathlib
import sys
import time

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())
sp = sys.argv[1] if len(sys.argv) > 1 else "rose"
bloom = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
node = hou.node("/obj").createNode("geo").createNode("ksd::flower_generator::1.0")
node.parm("species").set(sp)
node.hdaModule().apply_species(node)
node.parm("bloom").set(bloom)
node.geometry()
rows = []
for child in node.children():
    best = 1e9
    for _ in range(3):
        t0 = time.perf_counter()
        child.cook(force=True)
        best = min(best, (time.perf_counter() - t0) * 1000)
    rows.append((best, child.name()))
rows.sort(reverse=True)
total = sum(r[0] for r in rows)
print(f"{sp} bloom={bloom}: sum of node cooks {total:.0f} ms")
for ms, name in rows[:8]:
    print(f"  {ms:7.1f} ms  {name}")
