"""Render Karma CPU previews of the Flower Generator.

usage: hython tools/render_preview.py OUT_DIR [species,...] [bloom,...] [res]
       defaults: every species, blooms 0,0.5,1, 480 px.

Writes OUT_DIR/<species>_b<bloom>.png (head close-ups) and OUT_DIR/<species>_plant.png.
CPU only, so it needs no GPU memory.
"""
import json
import pathlib
import sys

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
out_dir = pathlib.Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=True)
all_species = [k for k in json.loads((ROOT / "presets" / "species.json").read_text()) if not k.startswith("_")]
species = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else all_species
blooms = [float(b) for b in sys.argv[3].split(",")] if len(sys.argv) > 3 else [0.0, 0.5, 1.0]
res = int(sys.argv[4]) if len(sys.argv) > 4 else 480

hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())
obj = hou.node("/obj")
geo = obj.createNode("geo", "flower")
node = geo.createNode("ksd::flower_generator::1.0")

env = obj.createNode("envlight")
env.parmTuple("light_color").set((0.75, 0.78, 0.82))
key = obj.createNode("hlight::2.0", "key")
key.parm("light_type").set("distant")
key.parm("light_intensity").set(2.5)
key.parmTuple("r").set((-50, -35, 0))

cam = obj.createNode("cam")
cam.parm("resx").set(res)
cam.parm("resy").set(res)
cam.parm("near").set(0.0005)

karma = hou.node("/out").createNode("karma")
karma.parm("camera").set(cam.path())
karma.parm("engine").set("cpu")
karma.parm("samplesperpixel").set(24)
karma.parm("resolutionx").set(res)
karma.parm("resolutiony").set(res)


def look_at(eye, target):
    eye, target = hou.Vector3(eye), hou.Vector3(target)
    z = (eye - target).normalized()
    x = hou.Vector3(0, 1, 0).cross(z).normalized()
    y = z.cross(x)
    return hou.Matrix4(((x[0], x[1], x[2], 0), (y[0], y[1], y[2], 0),
                        (z[0], z[1], z[2], 0), (eye[0], eye[1], eye[2], 1)))


def frame(bbox, direction, fill=1.15):
    c = bbox.center()
    radius = max(bbox.sizevec()) * 0.5 * fill
    d = hou.Vector3(direction).normalized()
    # 50 mm on a 41.4 mm aperture: half field of view of about 22.5 degrees.
    dist = radius / 0.4
    cam.setWorldTransform(look_at(c + d * dist, c))


HEAD_PARTS = {"petal", "center", "floret", "stamen", "anther", "pistil", "sepal"}


def head_bbox(g):
    bb = None
    for prim in g.iterPrims():
        if prim.attribValue("part") in HEAD_PARTS:
            if bb is None:
                bb = prim.boundingBox()
            else:
                bb.enlargeToContain(prim.boundingBox())
    return bb


for sp in species:
    node.parm("species").set(sp)
    node.hdaModule().apply_species(node)
    for b in blooms:
        node.parm("bloom").set(b)
        frame(head_bbox(node.geometry()), (0.9, 0.75, 1.0))
        path = out_dir / f"{sp}_b{int(round(b * 100)):03d}.png"
        karma.parm("picture").set(path.as_posix())
        karma.render()
        print("wrote", path)
    node.parm("bloom").set(1.0)
    frame(node.geometry().boundingBox(), (1.0, 0.25, 1.0), fill=1.05)
    path = out_dir / f"{sp}_plant.png"
    karma.parm("picture").set(path.as_posix())
    karma.render()
    print("wrote", path)
