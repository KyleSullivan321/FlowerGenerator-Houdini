"""Render a bloom animation of one species as a PNG sequence (Karma CPU).

usage: hython tools/render_bloom.py OUT_DIR species [frames] [res]

The camera is framed on the fully open head and held, so the bloom reads
against a fixed view. Bloom runs 0 to 1 over the frames with a short hold
at each end.
"""
import pathlib
import sys

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
out_dir = pathlib.Path(sys.argv[1])
sp = sys.argv[2]
frames = int(sys.argv[3]) if len(sys.argv) > 3 else 60
res = int(sys.argv[4]) if len(sys.argv) > 4 else 360
out_dir.mkdir(parents=True, exist_ok=True)
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())

obj = hou.node("/obj")
node = obj.createNode("geo", "flower").createNode("ksd::flower_generator::1.0")
node.parm("species").set(sp)
node.hdaModule().apply_species(node)

env = obj.createNode("envlight")
env.parmTuple("light_color").set((0.7, 0.74, 0.8))
key = obj.createNode("hlight::2.0", "key")
key.parm("light_type").set("distant")
key.parm("light_intensity").set(2.8)
key.parmTuple("r").set((-50, -35, 0))
cam = obj.createNode("cam")
cam.parm("near").set(0.0005)
karma = hou.node("/out").createNode("karma")
karma.parm("camera").set(cam.path())
karma.parm("engine").set("cpu")
karma.parm("samplesperpixel").set(16)
karma.parm("resolutionx").set(res)
karma.parm("resolutiony").set(res)

HEAD = {"petal", "center", "floret", "stamen", "anther", "pistil", "sepal"}
node.parm("bloom").set(1.0)
bb = None
for prim in node.geometry().iterPrims():
    if prim.attribValue("part") in HEAD:
        if bb is None:
            bb = prim.boundingBox()
        else:
            bb.enlargeToContain(prim.boundingBox())
c = bb.center()
d = hou.Vector3(0.9, 0.85, 1.0).normalized()
eye = c + d * (bb.sizevec().length() * 0.5 * 1.05 / 0.4)   # frame the bbox diagonal
z = (eye - c).normalized()
x = hou.Vector3(0, 1, 0).cross(z).normalized()
y = z.cross(x)
cam.setWorldTransform(hou.Matrix4(((x[0], x[1], x[2], 0), (y[0], y[1], y[2], 0),
                                   (z[0], z[1], z[2], 0), (eye[0], eye[1], eye[2], 1))))

hold = max(1, frames // 10)
for f in range(frames):
    b = min(1.0, max(0.0, (f - hold) / max(1, frames - 2 * hold - 1)))
    node.parm("bloom").set(b)
    karma.parm("picture").set((out_dir / f"{sp}.{f:04d}.png").as_posix())
    karma.render()
print("wrote", frames, "frames to", out_dir)
