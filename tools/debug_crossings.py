"""Render the flower head with every triangle that crosses another part painted red.

usage: hython tools/debug_crossings.py OUT.png species bloom [deintersect 0|1] [view x,y,z]
"""
import pathlib
import sys

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
out, sp, bloom = sys.argv[1], sys.argv[2], float(sys.argv[3])
on = int(sys.argv[4]) if len(sys.argv) > 4 else 1
view = [float(v) for v in sys.argv[5].split(",")] if len(sys.argv) > 5 else [0.9, 0.75, 1.0]
hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())

obj = hou.node("/obj")
src = obj.createNode("geo", "src")
node = src.createNode("ksd::flower_generator::1.0")
node.parm("species").set(sp)
node.hdaModule().apply_species(node)
node.parm("bloom").set(bloom)
node.parm("deintersect").set(on)

geo = obj.createNode("geo", "debug")
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
paint = geo.createNode("attribwrangle")
paint.setInput(0, tris)
paint.setInput(1, classify)
paint.parm("class").set("point")
paint.parm("snippet").set("""
int near[] = pcfind(1, "P", v@P, 0.0012, 1);
foreach (int q; near) if (point(1, "crossing", q)) v@Cd = {1, 0, 0};
""")
paint.setDisplayFlag(True)
paint.setRenderFlag(True)
src.setDisplayFlag(False)

env = obj.createNode("envlight")
env.parmTuple("light_color").set((0.75, 0.78, 0.82))
key = obj.createNode("hlight::2.0", "key")
key.parm("light_type").set("distant")
key.parm("light_intensity").set(2.5)
key.parmTuple("r").set((-50, -35, 0))
cam = obj.createNode("cam")
cam.parm("near").set(0.0005)
bb = paint.geometry().boundingBox()
c = bb.center()
d = hou.Vector3(view).normalized()
eye = c + d * (max(bb.sizevec()) * 0.5 * 1.15 / 0.4)
z = (eye - c).normalized()
x = hou.Vector3(0, 1, 0).cross(z).normalized()
y = z.cross(x)
cam.setWorldTransform(hou.Matrix4(((x[0], x[1], x[2], 0), (y[0], y[1], y[2], 0),
                                   (z[0], z[1], z[2], 0), (eye[0], eye[1], eye[2], 1))))
karma = hou.node("/out").createNode("karma")
karma.parm("camera").set(cam.path())
karma.parm("engine").set("cpu")
karma.parm("samplesperpixel").set(16)
karma.parm("resolutionx").set(512)
karma.parm("resolutiony").set(512)
karma.parm("picture").set(pathlib.Path(out).as_posix())
karma.render()
print("wrote", out)
