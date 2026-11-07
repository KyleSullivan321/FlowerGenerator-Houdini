"""Time a species with the de-intersect pass on and off.

usage: hython tests/profile_cook.py [species] [bloom]
"""
import pathlib
import sys
import time

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())
sp = sys.argv[1] if len(sys.argv) > 1 else "rose"
bloom = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
node = hou.node("/obj").createNode("geo").createNode("ksd::flower_generator::1.0")
node.parm("species").set(sp)
node.hdaModule().apply_species(node)
node.geometry()  # compile
for on in (0, 1):
    node.parm("deintersect").set(on)
    times = []
    for k in range(3):
        node.parm("bloom").set(bloom + 0.001 * k)
        t0 = time.perf_counter()
        g = node.geometry()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"{sp} bloom={bloom} deintersect={on}: {min(times):.0f} ms, bbox "
          f"{', '.join(f'{v:.3f}' for v in g.boundingBox().sizevec())}")
