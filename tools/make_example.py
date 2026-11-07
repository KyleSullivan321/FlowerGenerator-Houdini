"""Write examples/flower_generator_demo.hip(lc): three flowers with timed blooms, lights and a Karma ROP.

usage: hython tools/make_example.py
"""
import pathlib

import hou

ROOT = pathlib.Path(__file__).resolve().parents[1]
hda = next((ROOT / "otls").glob("ksd_flower_generator.hda*"))
hou.hda.installFile(hda.as_posix())
hou.hipFile.clear(suppress_save_prompt=True)
hou.playbar.setFrameRange(1, 120)
hou.setFps(24)

obj = hou.node("/obj")
for i, (sp, x, start) in enumerate((("rose", -0.12, 1), ("tulip", 0.0, 20), ("daisy", 0.12, 40))):
    geo = obj.createNode("geo", sp)
    geo.parmTuple("t").set((x, 0, 0))
    node = geo.createNode("ksd::flower_generator::1.0", sp)
    node.parm("species").set(sp)
    node.hdaModule().apply_species(node)
    node.parm("anim_mode").set(1)
    node.parm("bloom_start").set(start)
    node.parm("bloom_duration").set(72)
    node.setDisplayFlag(True)
    node.setRenderFlag(True)

env = obj.createNode("envlight", "sky")
env.parmTuple("light_color").set((0.7, 0.74, 0.8))
key = obj.createNode("hlight::2.0", "key")
key.parm("light_type").set("distant")
key.parm("light_intensity").set(2.8)
key.parmTuple("r").set((-50, -35, 0))
cam = obj.createNode("cam", "shot")
cam.parm("near").set(0.001)
cam.parmTuple("t").set((0.0, 0.42, 0.75))
cam.parmTuple("r").set((-12, 0, 0))
cam.parm("resx").set(1920)
cam.parm("resy").set(1080)

karma = hou.node("/out").createNode("karma", "karma_preview")
karma.parm("camera").set(cam.path())
karma.parm("engine").set("cpu")
karma.parm("picture").set("$HIP/render/flower_demo.$F4.exr")

obj.layoutChildren()
out = ROOT / "examples" / ("flower_generator_demo.hiplc" if hda.suffix == ".hdalc" else "flower_generator_demo.hip")
hou.hipFile.save(out.as_posix())
print("saved", out)
