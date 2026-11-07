# PythonModule of the Flower Generator HDA. The build script prepends
# SPECIES = {...} (the presets from presets/species.json) above this code.
import random

import hou

# Parameters a species change leaves alone.
KEEP = {"species", "seed", "flower_scale", "anim_mode", "bloom", "bloom_start",
        "bloom_duration", "peel", "overshoot", "petal_rows", "petal_cols",
        "stem_segments", "stem_sides", "deintersect", "deintersect_res",
        "deintersect_gap", "deintersect_reach", "deintersect_smooth", "deintersect_angle",
        "cache_file", "load_from_disk"}
# deintersect_center is per species, so a species change sets it.


def _set(node, name, value):
    pt = node.parmTuple(name)
    if pt is None:
        return
    if isinstance(pt.parmTemplate(), hou.RampParmTemplate):
        keys = [k[0] for k in value]
        vals = [k[1] for k in value]
        pt[0].set(hou.Ramp([hou.rampBasis.CatmullRom] * len(keys), keys, vals))
    elif isinstance(value, (list, tuple)):
        pt.set(value)
    else:
        pt[0].set(value)


def apply_species(node, name=None):
    name = name or node.parm("species").evalAsString()
    if name == "custom":  # keep every current value
        return
    preset = SPECIES.get(name)  # noqa: F821 (defined by the build script)
    if not preset:
        return
    with hou.undos.group("Apply flower species"):
        for pt in node.parmTuples():
            tmpl = pt.parmTemplate()
            if pt.name() in KEEP or isinstance(tmpl, (hou.FolderSetParmTemplate,
                                                       hou.ButtonParmTemplate,
                                                       hou.SeparatorParmTemplate)):
                continue
            try:
                pt.revertToDefaults()
            except hou.OperationFailed:
                pass
        for key, value in preset.items():
            if key == "label":
                continue
            _set(node, key, value)


def randomize(node):
    node.parm("seed").set(random.randint(0, 9999))


def bake_frames(node):
    """Frames to bake: the timed bloom span, or the playbar range in Bloom Slider mode."""
    if node.parm("anim_mode").evalAsString() == "time":
        a = node.parm("bloom_start").eval()
        b = a + node.parm("bloom_duration").eval()
        return range(int(round(a)), int(round(b)) + 1)
    lo, hi = hou.playbar.frameRange()
    return range(int(round(lo)), int(round(hi)) + 1)


def save_to_disk(node, frames=None, interactive=True):
    """Cook the live flower at each frame and write it to the cache file.

    Never moves the global frame: each frame is evaluated with geometryAtFrame, so the
    viewport is not redrawn per frame. Esc cancels (files already written stay).
    Returns the list of written paths."""
    import os
    import time
    live = node.node("normals")
    frames = list(frames if frames is not None else bake_frames(node))
    cache_parm = node.parm("cache_file")
    total = len(frames)
    written = []
    t0 = time.time()
    folder = ""
    try:
        with hou.InterruptableOperation("Baking flower", long_operation_name="Baking flower",
                                        open_interrupt_dialog=interactive) as op:
            for i, f in enumerate(frames):
                op.updateLongProgress(i / max(1, total), "Frame %d of %d" % (i + 1, total))
                path = cache_parm.evalAtFrame(f)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                live.geometryAtFrame(f).saveToFile(path)
                written.append(path)
                folder = os.path.dirname(path)
                if (i + 1) % 10 == 0:
                    print("Flower bake: frame %d of %d" % (i + 1, total))
    except hou.OperationInterrupted:
        print("Flower bake cancelled after %d of %d frames" % (len(written), total))
    msg = "Baked %d frames in %.0f s to %s" % (len(written), time.time() - t0, folder)
    print(msg)
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(msg)
    return written
