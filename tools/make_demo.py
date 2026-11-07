"""Build, render and encode the rose demo video (docs/media/rose_demo.mp4).

Scene and capture (Houdini 22, hython):
    hython tools/make_demo.py [--renderer opengl|karma] [--out DIR] [--scale S] [--step N]
                              [--frames A-B] [--spp N] [--engine cpu|xpu] [--save-hip]
                              [--no-render] [--no-finish] [--final]
Captions and encode (Python 3 with Pillow, ffmpeg on PATH; run automatically after a render):
    python tools/make_demo.py finish --out DIR [--step N] [--final]

The scene is saved as examples/demo/rose_demo.hiplc: every parameter change in the video is a
keyframe on the Flower Generator node, so opening the file and pressing play shows the same demo.
Frames are viewport captures from the OpenGL ROP by default (smooth shaded, the node's own
colours, scene lights with shadows); --renderer karma renders with Karma instead (CPU, or XPU
with --engine xpu). Frames go to DIR/raw, captioned frames to DIR/comp.
--scale .3333 --step 3 makes the quick proof (640x360, every 3rd frame).
"""
import argparse
import json
import math
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
FPS = 24
TOTAL = 528                      # 22 s
SHOTS = {                        # inclusive frame ranges
    "head": (1, 312),
    "leaves": (313, 384),
    "bloom": (385, TOTAL),
}
# Captions use the node's own labels: (tab, label) as they appear in the parameter interface.
BEATS = [
    {"key": "species", "tab": "Flower", "label": "Species", "start": 1, "end": 72, "fade_in_at": 10},
    {"key": "petal_count", "tab": "Petals", "label": "Petal Count", "start": 73, "end": 156},
    {"key": "color", "tab": "Petals", "label": "Color", "start": 157, "end": 240},
    {"key": "seed", "tab": "Flower", "label": "Seed", "start": 241, "end": 312},
    {"key": "leaf_rotate_random", "tab": "Leaves", "label": "Random Rotation", "start": 313, "end": 384},
    {"key": "anim_mode", "tab": "Animation", "label": "Mode", "start": 385, "end": 470},
]
TITLE = {"text": "Flower Generator for Houdini", "start": 480}

BACKDROP_CD = (0.11, 0.10, 0.092)                   # warm dark grey (viewport capture)
CRIMSON = ((0.45, 0.02, 0.06), (0.85, 0.08, 0.18))   # rose preset (Base, Tip)
BLUSH = ((0.80, 0.20, 0.30), (0.96, 0.48, 0.56))
APRICOT = ((0.90, 0.28, 0.05), (1.00, 0.56, 0.20))
IVORY = ((0.74, 0.64, 0.44), (0.92, 0.88, 0.74))

# (frame, value). Integers step (constant keys); colours and angles ease between keys.
PETAL_COUNT = [(1, 40), (87, 24), (101, 32), (115, 48), (129, 64), (143, 40)]
COLOR = [(1, CRIMSON), (164, CRIMSON), (181, BLUSH), (188, BLUSH), (205, APRICOT), (212, APRICOT),
         (229, IVORY), (312, IVORY), (313, CRIMSON)]
SEED = [(1, 1), (259, 7), (277, 42), (295, 99), (313, 1)]
LEAF_ROT = [(1, 40), (312, 40), (313, 0), (324, 0), (368, 120), (384, 120), (385, 40)]
ANIM_MODE = [(1, 0), (385, 1)]           # Bloom Slider, then Timed Bloom
BLOOM_START, BLOOM_DURATION = 393, 104   # bud until 393; petals settle at bloom .76 (f472)


# --------------------------------------------------------------------------------------------
# Scene (hython)
# --------------------------------------------------------------------------------------------

def _key(parm, frame, value, expr):
    import hou
    k = hou.Keyframe()
    k.setFrame(frame)
    k.setValue(value)
    k.setExpression(expr)
    parm.setKeyframe(k)


def _key_list(parm, keys, expr):
    parm.deleteAllKeyframes()
    for f, v in keys:
        _key(parm, f, v, expr)


def _look_at(eye, target):
    import hou
    eye, target = hou.Vector3(eye), hou.Vector3(target)
    z = (eye - target).normalized()
    x = hou.Vector3(0, 1, 0).cross(z).normalized()
    y = z.cross(x)
    return hou.Matrix4(((x[0], x[1], x[2], 0), (y[0], y[1], y[2], 0),
                        (z[0], z[1], z[2], 0), (eye[0], eye[1], eye[2], 1)))


def _fit(points, target, direction, tan_h, aspect, fill_w, fill_h, screen=(0.0, 0.0)):
    """Eye position looking along -direction at `target` so `points` reach at most fill_w, fill_h
    (NDC, -1..1) from the target, then aimed so the target lands at `screen`. Returns (eye, aim)."""
    import hou
    d = hou.Vector3(direction).normalized()
    x = hou.Vector3(0, 1, 0).cross(d).normalized()
    y = d.cross(x)
    tan_v = tan_h / aspect
    lo, hi = 0.01, 20.0
    for _ in range(60):
        dist = 0.5 * (lo + hi)
        eye = target + d * dist
        fits = True
        for p in points:
            v = p - eye
            depth = -v.dot(d)
            if depth <= 1e-4:
                fits = False
                break
            sx = v.dot(x) / depth / tan_h
            sy = v.dot(y) / depth / tan_v
            if abs(sx) > fill_w or abs(sy) > fill_h:
                fits = False
                break
        hi, lo = (dist, lo) if fits else (hi, dist)
    dist = hi
    eye = target + d * dist
    # Aim off the target so the target lands at `screen`.
    aim = target - x * (screen[0] * tan_h * dist) - y * (screen[1] * tan_v * dist)
    return eye, aim


def _part_points(geo, parts, every=7):
    import hou
    pts = []
    for prim in geo.iterPrims():
        if prim.attribValue("part") in parts:
            for i, v in enumerate(prim.vertices()):
                if i % every == 0:
                    pts.append(hou.Vector3(v.point().position()))
    return pts


def _center(pts):
    """Centre of the bounding box of a list of hou.Vector3."""
    import hou
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return hou.Vector3([(a + b) * 0.5 for a, b in zip(lo, hi)])


def _mtlx_material(mat_ctx, name, base_color, use_cd=False, specular=0.3, roughness=0.45,
                   sheen=0.0, translucency=0.0):
    import voptoolutils
    sub = voptoolutils._setupMtlXBuilderSubnet(
        destination_node=mat_ctx, name=name, mask=voptoolutils.KARMAMTLX_TAB_MASK,
        folder_label="Karma Material Builder", render_context="kma")
    surf = sub.node("mtlxstandard_surface")
    surf.parmTuple("base_color").set(base_color)
    surf.parm("base").set(1.0)
    surf.parm("specular").set(specular)
    surf.parm("specular_roughness").set(roughness)
    if sheen:
        surf.parm("sheen").set(sheen)
        surf.parm("sheen_roughness").set(0.45)
    if translucency:
        surf.parm("thin_walled").set(1)
        surf.parm("subsurface").set(translucency)
    if use_cd:
        cd = sub.createNode("mtlxgeompropvalue", "cd")
        cd.parm("signature").set("color3")
        cd.parm("geomprop").set("displayColor")
        cd.parmTuple("default_color3").set(base_color)
        surf.setNamedInput("base_color", cd, 0)
        if translucency:
            surf.setNamedInput("subsurface_color", cd, 0)
        if sheen:
            surf.setNamedInput("sheen_color", cd, 0)
    sub.layoutChildren()
    return sub


def build_scene(scale=1.0, spp=24, engine="cpu", renderer="opengl"):
    import hou
    hou.hda.installFile(next((ROOT / "otls").glob("ksd_flower_generator.hda*")).as_posix())
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.setFps(FPS)
    hou.playbar.setFrameRange(1, TOTAL)
    hou.playbar.setPlaybackRange(1, TOTAL)
    obj = hou.node("/obj")
    mat = hou.node("/mat")

    # Flower: the rose preset, every change below is a keyframe.
    geo = obj.createNode("geo", "rose")
    node = geo.createNode("ksd::flower_generator::1.0", "flower_generator")
    node.parm("species").set("rose")
    node.hdaModule().apply_species(node)
    node.setDisplayFlag(True)
    node.setRenderFlag(True)

    # Framing references, measured on the open default rose.
    node.parm("bloom").set(1.0)
    g = node.geometry()
    head_parts = {"petal", "center", "sepal", "stamen", "anther", "pistil"}
    head_pts = _part_points(g, head_parts)
    head_c = _center(head_pts)
    plant_pts = _part_points(g, head_parts | {"leaf", "stem", "thorn"}, every=11)
    upper = [p for p in plant_pts if p[1] > 0.09]              # leaves and head
    upper_c = _center(upper)

    _key_list(node.parm("petal_count"), PETAL_COUNT, "constant()")
    for i, comp in enumerate("rgb"):
        _key_list(node.parm("color_base" + comp), [(f, c[0][i]) for f, c in COLOR], "ease()")
        _key_list(node.parm("color_tip" + comp), [(f, c[1][i]) for f, c in COLOR], "ease()")
    _key_list(node.parm("seed"), SEED, "constant()")
    _key_list(node.parm("leaf_rotate_random"), LEAF_ROT, "ease()")
    _key_list(node.parm("anim_mode"), ANIM_MODE, "constant()")
    node.parm("bloom").set(1.0)
    node.parm("bloom_start").set(BLOOM_START)
    node.parm("bloom_duration").set(BLOOM_DURATION)

    # Materials: petals read their colour from Cd (displayColor), a little sheen and translucency.
    viewport = renderer == "opengl"
    petal_mat = _mtlx_material(mat, "petal", (0.5, 0.1, 0.1), use_cd=True, specular=0.3,
                               roughness=0.45, sheen=0.35, translucency=0.15)
    foliage_mat = _mtlx_material(mat, "foliage", (0.1, 0.25, 0.08), use_cd=True, specular=0.4,
                                 roughness=0.38, translucency=0.1)
    back_mat = _mtlx_material(mat, "backdrop", (0.05, 0.044, 0.04), specular=0.1, roughness=0.8)
    assign = geo.createNode("attribwrangle", "assign_materials")
    assign.setInput(0, node)
    assign.parm("class").set("primitive")
    assign.parm("snippet").set(
        's@shop_materialpath = s@part == "petal" || s@part == "center" || s@part == "stamen" '
        '|| s@part == "anther" || s@part == "pistil" ? "%s" : "%s";' % (petal_mat.path(), foliage_mat.path()))
    assign.setDisplayFlag(True)
    assign.setRenderFlag(True)
    if viewport:          # viewport capture: the node's own colours, no materials
        assign.bypass(True)

    # Camera and shots.
    res = (int(round(1920 * scale)), int(round(1080 * scale)))
    cam = obj.createNode("cam", "shot")
    cam.parm("resx").set(res[0])
    cam.parm("resy").set(res[1])
    cam.parm("focal").set(85)
    cam.parm("aperture").set(41.4214)
    cam.parm("near").set(0.005)
    cam.parm("far").set(50)
    tan_h = 41.4214 * 0.5 / 85
    aspect = 1920 / 1080
    def az_el(az, el):
        a, e = math.radians(az), math.radians(el)
        return hou.Vector3(math.sin(a) * math.cos(e), math.sin(e), math.cos(a) * math.cos(e))

    # 3/4 hero view, 40 deg above; at this azimuth no leaf reaches the caption corner for the
    # seeds used (checked by projection). The leaves shot looks square onto the leaf plane.
    views = {"head": az_el(70, 40), "leaves": az_el(12, 28), "bloom": az_el(70, 32)}
    shots = {
        # Head fills a bit over half the frame height, set right of centre (captions sit lower left).
        "head": _fit(head_pts, head_c, views["head"], tan_h, aspect, 0.5, 0.62, screen=(0.24, 0.08)),
        "leaves": _fit(upper, upper_c, views["leaves"], tan_h, aspect, 0.66, 0.86, screen=(0.2, 0.0)),
        "bloom": _fit(head_pts, head_c, views["bloom"], tan_h, aspect, 0.5, 0.66, screen=(0.22, 0.04)),
    }
    for name, (eye, aim) in shots.items():
        print("shot %-6s eye %s aim %s dist %.3f" % (name, [round(v, 3) for v in eye],
                                                    [round(v, 3) for v in aim], (eye - aim).length()))
    dolly = {"head": 0.05, "leaves": 0.035, "bloom": 0.04}   # slow straight push over each shot
    for p in ("tx", "ty", "tz", "rx", "ry", "rz"):
        cam.parm(p).deleteAllKeyframes()
    for name, (f0, f1) in SHOTS.items():
        eye, aim = shots[name]
        m0 = _look_at(eye, aim)
        eye1 = eye + (aim - eye) * dolly[name]
        r = m0.explode()["rotate"]
        for i, p in enumerate(("rx", "ry", "rz")):
            _key(cam.parm(p), f0, r[i], "constant()")
        for f, e in ((f0, eye), (f1, eye1)):
            for i, p in enumerate(("tx", "ty", "tz")):
                _key(cam.parm(p), f, e[i], "linear()")

    # Backdrop: a seamless cyclorama, floor turning up into a wall behind the flower.
    back = obj.createNode("geo", "backdrop")
    grid = back.createNode("grid")
    grid.parm("type").set("poly")
    grid.parmTuple("size").set((4, 4))
    grid.parm("rows").set(160)
    grid.parm("cols").set(40)
    bend = back.createNode("attribwrangle", "cyclorama")
    bend.setInput(0, grid)
    bend.parm("snippet").set(
        "float z0 = -0.75, R = 0.6;\n"
        "float s = z0 - @P.z;\n"
        "if (s > 0) {\n"
        "    float a = s / R;\n"
        "    if (a < PI / 2) { @P.y = R * (1 - cos(a)); @P.z = z0 - R * sin(a); }\n"
        "    else { @P.y = R + (s - R * PI / 2); @P.z = z0 - R; }\n"
        "}\n")
    nrm = back.createNode("normal")
    nrm.setInput(0, bend)
    col = back.createNode("color", "backdrop_color")
    col.setInput(0, nrm)
    col.parmTuple("color").set(BACKDROP_CD)
    col.setDisplayFlag(True)
    col.setRenderFlag(True)
    if not viewport:
        back.parm("shop_materialpath").set(back_mat.path())
    back.parmTuple("t").set((head_c[0], 0, head_c[2]))

    def heading(v):
        return math.atan2(v[0], v[2])

    # The wall turns with each shot (keyed at the cuts) so it always sits behind the flower.
    for name, (f0, _f1) in SHOTS.items():
        _key(back.parm("ry"), f0, math.degrees(heading(views[name])), "constant()")

    # Light: soft key upper left of camera, rim from behind right, dim dome fill. The rig is
    # placed relative to each shot's camera and keyed at the cuts.
    def area(name, azim, elev, dist, size, intensity, color):
        lt = obj.createNode("hlight::2.0", name)
        lt.parm("light_type").set("grid")
        lt.parm("areasize1").set(size)
        lt.parm("areasize2").set(size)
        lt.parm("light_intensity").set(intensity)
        lt.parmTuple("light_color").set(color)
        for shot, (f0, _f1) in SHOTS.items():
            a = heading(views[shot]) + math.radians(azim)
            e = math.radians(elev)
            pos = head_c + hou.Vector3(math.sin(a) * math.cos(e), math.sin(e), math.cos(a) * math.cos(e)) * dist
            m = _look_at(pos, head_c).explode()
            for i, c in enumerate("xyz"):
                _key(lt.parm("t" + c), f0, m["translate"][i], "constant()")
                _key(lt.parm("r" + c), f0, m["rotate"][i], "constant()")
        return lt

    area("key", -55, 48, 1.1, 0.7, 0.62, (1.0, 0.96, 0.9))
    area("rim", 150, 35, 0.9, 0.35, 0.5, (0.92, 0.96, 1.0))
    env = obj.createNode("envlight", "fill")
    env.parmTuple("light_color").set((0.05, 0.05, 0.053))

    if viewport:
        rop = hou.node("/out").createNode("opengl", "viewport_demo")
        rop.parm("camera").set(cam.path())
        rop.parm("tres").set(1)
        rop.parm("res1").set(res[0])
        rop.parm("res2").set(res[1])
        rop.parm("aamode").set("aa16")
        rop.parm("shadingmode").set("smooth")
        rop.parm("usegeocolor").set(1)
        rop.parm("hqlighting").set(1)
        rop.parm("lightsamples").set(64)
        rop.parm("shadows").set(1)
        rop.parm("shadowquality").set("areaaa")
        rop.parm("shadowmap").set(4096)
        rop.parm("ambocclusion").set(0)      # screen-space AO adds grain on thin petals
        rop.parm("usehdr").set("on")
        rop.parm("colorcorrect").set("lut_gamma")
        rop.parm("gamma").set(2.2)
        rop.parm("picture").set("$HIP/render/rose_demo.$F4.png")
        # Viewport lighting is not physically scaled like Karma: lift the rig to a matching exposure.
        for name, gain in (("key", 2.2), ("rim", 1.6), ("fill", 2.8)):
            lp = obj.node(name).parm("light_intensity")
            lp.set(lp.eval() * gain)
        obj.layoutChildren()
        return node, rop, cam
    karma = hou.node("/out").createNode("karma", "karma_demo")
    karma.parm("camera").set(cam.path())
    karma.parm("engine").set(engine)
    karma.parm("allframesatonce").set(1)      # one husk process for the whole frame range
    karma.parm("resolutionx").set(res[0])
    karma.parm("resolutiony").set(res[1])
    karma.parm("samplesperpixel").set(spp)
    karma.parm("picture").set("$HIP/render/rose_demo.$F4.png")
    obj.layoutChildren()
    return node, karma, cam


def write_values(node, out):
    """Per-frame values of the captioned parameters, read back from the keyed node."""
    vals = {}
    for f in range(1, TOTAL + 1):
        vals[f] = {
            "petal_count": int(node.parm("petal_count").evalAtFrame(f)),
            "seed": int(node.parm("seed").evalAtFrame(f)),
            "color_base": [node.parm("color_base" + c).evalAtFrame(f) for c in "rgb"],
            "color_tip": [node.parm("color_tip" + c).evalAtFrame(f) for c in "rgb"],
            "leaf_rotate_random": node.parm("leaf_rotate_random").evalAtFrame(f),
            "anim_mode": node.parm("anim_mode").evalAtFrame(f),
        }
    (out / "values.json").write_text(json.dumps(vals, indent=0))


def hython_main(args):
    import hou
    out = pathlib.Path(args.out).resolve()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    node, karma, cam = build_scene(args.scale, args.spp, args.engine, args.renderer)
    hip = ROOT / "examples" / "demo" / "rose_demo.hiplc"
    hip.parent.mkdir(parents=True, exist_ok=True)
    if args.save_hip:
        hou.hipFile.save(hip.as_posix())
        print("saved", hip)
    write_values(node, out)
    if args.no_render:
        return
    karma.parm("picture").set((out / "raw" / "rose_demo.$F4.png").as_posix())
    if args.frames:
        a, b = (int(v) for v in args.frames.split("-"))
    else:
        a, b = 1, TOTAL
    frames = list(range(a, b + 1, args.step))
    if args.list:
        frames = [int(v) for v in args.list.split(",")]
    t0 = time.time()
    if args.list:
        for f in frames:
            karma.render(frame_range=(f, f), verbose=False)
    else:
        karma.render(frame_range=(a, b, args.step), verbose=False)
    dt = time.time() - t0
    print("RENDER DONE %d frames in %.0fs (%.1fs per frame)" % (len(frames), dt, dt / max(1, len(frames))))
    if not args.no_finish:
        # The finish step needs a Python with Pillow, not Houdini's bundled one.
        import os
        hfs = os.path.normcase(os.environ.get("HFS", "")) or "<no HFS>"
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH")}
        env["PATH"] = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                                      if hfs not in os.path.normcase(d))
        py = shutil.which("python", path=env["PATH"]) or "python"
        cmd = [py, str(pathlib.Path(__file__).resolve()), "finish", "--out", str(out),
               "--step", str(args.step)]
        if args.final:
            cmd.append("--final")
        subprocess.run(cmd, check=True, env=env)


# --------------------------------------------------------------------------------------------
# Captions, poster, contact sheet and encode (Python 3 + Pillow + ffmpeg)
# --------------------------------------------------------------------------------------------

FONT_DIR = pathlib.Path("C:/Windows/Fonts")


def _font(name, size):
    from PIL import ImageFont
    for cand in (FONT_DIR / name, pathlib.Path(name)):
        if cand.exists():
            return ImageFont.truetype(str(cand), size)
    return ImageFont.load_default()


def _srgb(c):
    out = []
    for v in c:
        v = max(0.0, min(1.0, v))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(int(round(v * 255)))
    return tuple(out)


def _ramp(f, a, b):
    if b == a:
        return 1.0 if f >= a else 0.0
    t = max(0.0, min(1.0, (f - a) / (b - a)))
    return t * t * (3 - 2 * t)


def caption_state(f, vals):
    """Which caption shows at frame f, its pieces and its opacity."""
    for beat in BEATS:
        if beat["start"] <= f <= beat["end"]:
            fade_at = beat.get("fade_in_at", beat["start"])
            alpha = _ramp(f, fade_at, fade_at + 7) * (1 - _ramp(f, beat["end"] - 6, beat["end"]))
            v = vals[str(f)]
            k = beat["key"]
            if k == "species":
                value = [("text", "Rose")]
            elif k == "petal_count":
                value = [("text", str(v["petal_count"]))]
            elif k == "seed":
                value = [("text", str(v["seed"]))]
            elif k == "leaf_rotate_random":
                value = [("text", "%d\u00b0" % round(v["leaf_rotate_random"]))]
            elif k == "anim_mode":
                value = [("text", "Timed Bloom" if round(v["anim_mode"]) == 1 else "Bloom Slider")]
            else:  # colour
                value = [("label", "Base"), ("swatch", v["color_base"]),
                         ("label", "Tip"), ("swatch", v["color_tip"])]
            return beat, value, alpha
    return None, None, 0.0


def draw_caption(im, f, vals):
    from PIL import Image, ImageDraw
    W, H = im.size
    s = H / 1080.0
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, base = int(72 * s), int(H - 70 * s)
    beat, value, alpha = caption_state(f, vals)
    if beat and alpha > 0:
        a = int(255 * alpha)
        f_reg = _font("segoeui.ttf", max(10, int(27 * s)))
        f_semi = _font("seguisb.ttf", max(10, int(27 * s)))
        x = x0
        pieces = [("muted", beat["tab"]), ("muted", "\u203a"), ("label", beat["label"]), ("gap", None)] + value
        for kind, txt in pieces:
            if kind == "gap":
                x += int(14 * s)
                continue
            if kind == "swatch":
                sz = int(20 * s)
                top = base - int(21 * s)
                d.rounded_rectangle((x, top, x + sz, top + sz), radius=max(1, int(4 * s)),
                                    fill=_srgb(txt) + (a,), outline=(255, 255, 255, int(a * 0.55)),
                                    width=max(1, int(1.2 * s)))
                x += sz + int(18 * s)
                continue
            font = f_semi if kind == "text" else f_reg
            col = {"muted": (255, 255, 255, int(a * 0.5)), "label": (255, 255, 255, int(a * 0.82)),
                   "text": (255, 255, 255, a)}[kind]
            d.text((x, base), txt, font=font, fill=col, anchor="ls")
            x += int(d.textlength(txt, font=font)) + int(10 * s)
    if f >= TITLE["start"]:
        a = int(255 * _ramp(f, TITLE["start"], TITLE["start"] + 12))
        d.text((x0, base), TITLE["text"], font=_font("seguisb.ttf", max(10, int(32 * s))),
               fill=(255, 255, 255, int(a * 0.95)), anchor="ls")
    return Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")


def finish(args):
    from PIL import Image
    out = pathlib.Path(args.out)
    vals = json.loads((out / "values.json").read_text())
    raw = sorted((out / "raw").glob("rose_demo.*.png"))
    comp = out / "comp"
    if comp.exists():
        shutil.rmtree(comp)
    comp.mkdir()
    frames = []
    for i, p in enumerate(raw):
        f = int(p.stem.split(".")[-1])
        im = draw_caption(Image.open(p), f, vals)
        im.save(comp / ("c.%04d.png" % (i + 1)))
        frames.append(f)
    print("captioned", len(frames), "frames")

    # Contact sheet: one frame per beat and the bloom, captions included, 1024 px wide.
    picks = [40, 94, 136, 175, 196, 222, 262, 300, 318, 372, 388, 412, 436, 460, 490, 528]
    have = {f: i for i, f in enumerate(frames)}
    picks = [min(frames, key=lambda x: abs(x - p)) for p in picks]
    cols, cw = 4, 256
    ch = int(cw * 9 / 16)
    sheet = Image.new("RGB", (cols * cw, ((len(picks) + cols - 1) // cols) * ch))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for i, f in enumerate(picks):
        im = Image.open(comp / ("c.%04d.png" % (have[f] + 1)))
        im.thumbnail((cw, ch))
        sheet.paste(im, ((i % cols) * cw, (i // cols) * ch))
        dr.text(((i % cols) * cw + 4, (i // cols) * ch + 3), "f%d" % f, fill=(160, 160, 160))
    sheet.save(out / "sheet.jpg", quality=90)
    print("wrote", out / "sheet.jpg")

    rate = FPS / max(1, args.step)
    mp4 = out / "rose_demo.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "%g" % rate, "-i", str(comp / "c.%04d.png"),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17" if args.final else "22",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", "-r", str(FPS), str(mp4)]
    subprocess.run(cmd, check=True)
    print("wrote", mp4)
    if args.final:
        poster_f = min(frames, key=lambda x: abs(x - 500))
        Image.open(out / "raw" / ("rose_demo.%04d.png" % poster_f)).save(out / "rose_demo_poster.png")
        print("wrote", out / "rose_demo_poster.png", "(frame %d)" % poster_f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="render", choices=["render", "finish"])
    ap.add_argument("--out", default=str(ROOT / "renders" / "demo"))
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--frames", default="")
    ap.add_argument("--list", default="", help="comma-separated frames to render")
    ap.add_argument("--spp", type=int, default=24)
    ap.add_argument("--engine", default="cpu", choices=["cpu", "xpu"])
    ap.add_argument("--renderer", default="opengl", choices=["opengl", "karma"])
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-finish", action="store_true")
    ap.add_argument("--save-hip", action="store_true", help="write examples/demo/rose_demo.hiplc")
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args()
    if args.cmd == "finish":
        finish(args)
    else:
        hython_main(args)


if __name__ == "__main__":
    main()
