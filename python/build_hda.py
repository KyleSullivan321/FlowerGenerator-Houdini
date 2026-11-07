"""Build the Flower Generator HDA from the VEX and Python sources in this repo.

usage: hython python/build_hda.py [output.hda|.hdalc]

The default output is otls/ksd_flower_generator.hdalc on an Indie licence,
.hdanc on Apprentice or Education and .hda on a commercial one, so anyone can
rebuild the node under their own licence.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import hou  # noqa: E402
from flowergen import interface  # noqa: E402

TYPE_NAME = "ksd::flower_generator::1.0"
LABEL = "Flower Generator"
DEFAULT_SPECIES = "rose"
PETAL_POINT_ATTRIBS = ("petal_id order layerf azimuth scale alpha_open alpha_closed "
                       "pseed bloom alpha bend cup tipcurl roll lenscale wrap nest detail shell shell_scale")


def vex(name):
    """Snippet source with #include "x.h" lines replaced by vex/lib/x.h."""
    out = []
    for line in (ROOT / "vex" / f"{name}.vfl").read_text(encoding="utf-8").splitlines():
        if line.startswith("#include"):
            lib = line.split('"')[1]
            out.append(f"// ---- {lib} ----")
            out.append((ROOT / "vex" / "lib" / lib).read_text(encoding="utf-8"))
            out.append(f"// ---- end {lib} ----")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def wrangle(parent, name, run_over, inputs=(), code=None):
    w = parent.createNode("attribwrangle", name)
    w.parm("class").set(run_over)
    w.parm("snippet").set(vex(code or name))
    for i, n in enumerate(inputs):
        if n is not None:
            w.setInput(i, n)
    return w


def merge(parent, name, inputs):
    m = parent.createNode("merge", name)
    for i, n in enumerate(inputs):
        m.setInput(i, n)
    return m


G_EXPR = "\n".join([
    "b = ch('../bloom')",
    "g = b if ch('../anim_mode') == 0 else "
    "min(1.0, max(0.0, (hou.frame() - ch('../bloom_start')) / max(1e-3, ch('../bloom_duration')))) * b",
    "g = min(1.0, max(0.0, g))",
    "K = max(1, int(ch('../smooth_steps')))",
    "g0 = int(g * K + 1e-9) / float(K)",
    "return {KEY}"])
KEY_EXPR = {0: "g0", 1: "min(g0 + 1.0 / K, 1.0)"}


def key_parms(w, key):
    """Spare parms that pin a wrangle's bloom progress to bloom key 0 (floor) or 1 (next)."""
    t = w.parmTemplateGroup()
    t.append(hou.IntParmTemplate("g_override", "g_override", 1, default_value=(1,)))
    t.append(hou.FloatParmTemplate("g_fixed", "g_fixed", 1, default_value=(0.0,)))
    w.setParmTemplateGroup(t)
    w.parm("g_fixed").setExpression(G_EXPR.replace("{KEY}", KEY_EXPR[key]), hou.exprLanguage.Python)


def build_head(sub, layout, key=None):
    """The head parts, built at the current bloom (key None) or pinned to bloom key 0/1."""
    sfx = "" if key is None else f"_k{key}"
    pose = wrangle(sub, "petal_pose" + sfx, "point", [layout], code="petal_pose")
    petals = wrangle(sub, "petal_build" + sfx, "point", [pose], code="petal_build")
    clean = sub.createNode("attribdelete", "petal_clean" + sfx)
    clean.setInput(0, petals)
    clean.parm("ptdel").set(PETAL_POINT_ATTRIBS)
    center = wrangle(sub, "center" + sfx, "detail", code="center")
    stamens = wrangle(sub, "stamens" + sfx, "detail", code="stamens")
    sepals = wrangle(sub, "sepals" + sfx, "detail", [None, layout], code="sepals")
    if key is not None:
        for w in (pose, petals, center, stamens, sepals):
            key_parms(w, key)
    return merge(sub, "head" + sfx, [clean, center, stamens, sepals])


def build_deintersect(sub, head, layout):
    """Rank the head parts and resolve crossings. Returns the resolved head.

    With Smooth Animation on, the pass is solved at the two bloom keys around the
    current bloom and its displacement is blended between them."""
    rank = wrangle(sub, "rank", "primitive", [head])
    resolve = wrangle(sub, "deintersect", "detail", [rank])
    solved = []
    for key in (0, 1):
        h = build_head(sub, layout, key)
        r = wrangle(sub, f"rank_k{key}", "primitive", [h], code="rank")
        d = wrangle(sub, f"deintersect_k{key}", "detail", [r], code="deintersect")
        key_parms(d, key)
        solved.append(wrangle(sub, f"delta_k{key}", "point", [d, r], code="delta_keys"))
    blend = wrangle(sub, "blend_keys", "point", [rank, solved[0], solved[1]])
    switch = sub.createNode("switch", "deintersect_on")
    switch.setInput(0, rank)
    switch.setInput(1, resolve)
    switch.setInput(2, blend)
    switch.parm("input").setExpression('0 if ch("../deintersect") == 0 else (2 if ch("../smooth_anim") else 1)',
                                       hou.exprLanguage.Python)
    wrangle(sub, "check_intersections", "point", [switch])
    tidy = sub.createNode("attribdelete", "deintersect_clean")
    tidy.setInput(0, switch)
    tidy.parm("ptdel").set("nout")
    return tidy




def build_network(sub):
    stem = wrangle(sub, "stem", "detail")
    layout = wrangle(sub, "petal_layout", "detail")
    head = build_head(sub, layout)
    resolved = build_deintersect(sub, head, layout)
    place = wrangle(sub, "head_to_stem", "point", [resolved, stem])
    leaves = wrangle(sub, "leaves", "detail", [None, stem])
    thorns = wrangle(sub, "thorns", "detail", [None, stem])

    plant = merge(sub, "plant", [place, stem, leaves, thorns])
    scale = sub.createNode("xform", "overall_scale")
    scale.setInput(0, plant)
    scale.parm("scale").setExpression('ch("../flower_scale")')
    normals = sub.createNode("normal", "normals")
    normals.setInput(0, scale)
    normals.parm("cuspangle").set(60)
    cache = sub.createNode("file", "cache_read")
    cache.parm("missingframe").set("error")
    cache_sw = sub.createNode("switch", "cache_switch")
    cache_sw.setInput(0, normals)
    cache_sw.setInput(1, cache)
    cache_sw.parm("input").setExpression('ch("../load_from_disk")', hou.exprLanguage.Hscript)
    out = sub.createNode("output", "output0")
    out.setInput(0, cache_sw)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    sub.layoutChildren()


TOOLS_SHELF = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer">
      <contextNetType>SOP</contextNetType>
    </toolMenuContext>
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Flower</toolSubmenu>
    <script scriptType="python"><![CDATA[import soptoolutils
soptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
"""


def main():
    cat = hou.licenseCategory()
    lt = hou.licenseCategoryType
    if cat == lt.Indie:
        ext = "hdalc"
    elif cat in (lt.Apprentice, lt.ApprenticeHD, lt.Education):
        ext = "hdanc"
    else:
        ext = "hda"
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "otls" / ("ksd_flower_generator." + ext)
    out.parent.mkdir(parents=True, exist_ok=True)

    presets = json.loads((ROOT / "presets" / "species.json").read_text(encoding="utf-8"))
    presets = {k: v for k, v in presets.items() if not k.startswith("_")}
    items = [(k, v["label"]) for k, v in presets.items()] + [("custom", "Custom")]

    geo = hou.node("/obj").createNode("geo", "flower_build")
    sub = geo.createNode("subnet", "flower_generator")
    build_network(sub)

    node = sub.createDigitalAsset(name=TYPE_NAME, hda_file_name=out.as_posix(), description=LABEL,
                                  min_num_inputs=0, max_num_inputs=0,
                                  ignore_external_references=True)
    d = node.type().definition()
    d.setParmTemplateGroup(interface.build(presets[DEFAULT_SPECIES], items))
    # Set here, not in build_network: cache_file only exists once the interface is applied.
    node.node("cache_read").parm("file").setExpression('chs("../cache_file")', hou.exprLanguage.Hscript)

    module = ("import json\n"
              f"SPECIES = json.loads(r'''{json.dumps(presets, indent=1)}''')\n\n"
              + (ROOT / "python" / "flowergen" / "hda_module.py").read_text(encoding="utf-8"))
    d.addSection("PythonModule", module)
    d.setExtraFileOption("PythonModule/IsPython", True)
    d.addSection("Tools.shelf", TOOLS_SHELF)
    d.addSection("Help", (ROOT / "docs" / "help.txt").read_text(encoding="utf-8"))
    d.setIcon("SOP_lsystem")
    d.updateFromNode(node)
    d.save(out.as_posix(), node)
    print(f"built {TYPE_NAME} -> {out}")


if __name__ == "__main__":
    main()
