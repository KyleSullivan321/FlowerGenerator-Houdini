"""Bake a few frames to disk, load them back and compare point positions with the live cook.

usage: hython tests/cache_test.py
"""
import pathlib
import sys
import tempfile

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())
node = hou.node("/obj").createNode("geo", "cache_test").createNode("ksd::flower_generator::1.0")
tmp = pathlib.Path(tempfile.mkdtemp()).as_posix()
node.parm("cache_file").set(tmp + "/$OS/flower.$F4.bgeo.sc")
node.parm("anim_mode").set("time")
node.parm("bloom_start").set(1)
node.parm("bloom_duration").set(6)
assert list(node.hdaModule().bake_frames(node)) == list(range(1, 8)), "bake range"
frames = [1, 4, 7]
live = {}
for f in frames:
    hou.setFrame(f)
    live[f] = [p.position() for p in node.geometry().points()]
written = node.hdaModule().save_to_disk(node, frames, interactive=False)
assert len(written) == 3, written
node.parm("load_from_disk").set(1)
worst = 0.0
for f in frames:
    hou.setFrame(f)
    pts = [p.position() for p in node.geometry().points()]
    assert len(pts) == len(live[f]), f"point count at {f}"
    worst = max(worst, max((a - b).length() for a, b in zip(pts, live[f])))
print("worst position difference", worst)
assert worst < 1e-5
pathlib.Path(written[1]).unlink()
hou.setFrame(frames[1])
try:
    if node.geometry() is not None:
        raise SystemExit("load_from_disk did not read the files")
except hou.OperationFailed:
    pass
node.parm("load_from_disk").set(0)
assert len(node.geometry().points()) == len(live[frames[-1]])
print("CACHE OK")
