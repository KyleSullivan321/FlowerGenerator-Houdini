"""Parameter interface of the Flower Generator HDA.

Defaults for every parameter come from the default species preset, so a fresh
node shows a finished flower. Each builder below returns a hou.ParmTemplate.
"""
import hou

INTERP = {"catmull-rom": hou.rampBasis.CatmullRom, "linear": hou.rampBasis.Linear,
          "monotonecubic": hou.rampBasis.MonotoneCubic, "bspline": hou.rampBasis.BSpline}


_HIDE = {}


def _help(t, text):
    if text:
        t.setHelp(text)
    hide = _HIDE.pop("v", None)
    if hide:
        t.setConditional(hou.parmCondType.HideWhen, hide)
    return t


def _kw(kw):
    """Take hide_when out of the keyword args (the constructors lack it); _help applies it."""
    _HIDE["v"] = kw.pop("hide_when", None)
    return kw


def flt(name, label, d, lo=0.0, hi=1.0, help="", strict=False, **kw):
    _kw(kw)
    t = hou.FloatParmTemplate(name, label, 1, default_value=(float(d),), min=lo, max=hi,
                              min_is_strict=strict, **kw)
    return _help(t, help)


def int_(name, label, d, lo=0, hi=10, help="", strict=True, **kw):
    _kw(kw)
    t = hou.IntParmTemplate(name, label, 1, default_value=(int(d),), min=lo, max=hi,
                            min_is_strict=strict, **kw)
    return _help(t, help)


def toggle(name, label, d, help="", **kw):
    _kw(kw)
    return _help(hou.ToggleParmTemplate(name, label, default_value=bool(d), **kw), help)


def color(name, label, d, help="", **kw):
    _kw(kw)
    t = hou.FloatParmTemplate(name, label, 3, default_value=tuple(d), min=0, max=1,
                              look=hou.parmLook.ColorSquare,
                              naming_scheme=hou.parmNamingScheme.RGBA, **kw)
    return _help(t, help)


def menu(name, label, items, d=0, help="", callback=None, **kw):
    _kw(kw)
    t = hou.MenuParmTemplate(name, label, [i[0] for i in items], [i[1] for i in items],
                             default_value=d, **kw)
    if callback:
        t.setScriptCallback(callback)
        t.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return _help(t, help)


def ramp(name, label, keys, help="", interp="catmull-rom", **kw):
    _kw(kw)
    parts = []
    for i, (pos, val) in enumerate(keys, 1):
        parts.append(f"{i}pos ( {pos} ) {i}value ( {val} ) {i}interp ( {interp} )")
    t = hou.RampParmTemplate(name, label, hou.rampParmType.Float, default_value=len(keys),
                             tags={"rampfloatdefault": " ".join(parts),
                                   "rampshowcontrolsdefault": "0"}, **kw)
    return _help(t, help)


def button(name, label, script, help=""):
    t = hou.ButtonParmTemplate(name, label, script_callback=script,
                               script_callback_language=hou.scriptLanguage.Python)
    return _help(t, help)


def folder(label, parms, name=None, kind=hou.folderType.Tabs):
    f = hou.FolderParmTemplate(name or label.lower().replace(" ", "_"), label,
                               folder_type=kind)
    for p in parms:
        f.addParmTemplate(p)
    return f


_SUB_COUNT = [0]


def sub(label, parms):
    """A collapsible group inside a tab. Names are numbered so labels can repeat across tabs."""
    _SUB_COUNT[0] += 1
    return folder(label, parms, name=f"grp{_SUB_COUNT[0]}_" + label.lower().replace(" ", "_"),
                  kind=hou.folderType.Collapsible)


def build(d, species_items):
    """d: the default preset (name -> value). Returns a hou.ParmTemplateGroup."""
    g = hou.ParmTemplateGroup()

    flower = folder("Flower", [
        menu("species", "Species", species_items, 0,
             help="Loads a species preset into every tab. Change anything afterwards. Custom keeps "
                  "every current value, so you can start from any species and change what you like. "
                  "Save your own with the gear menu > Save Preset.",
             callback="hou.phm().apply_species(kwargs['node'])"),
        int_("seed", "Seed", 1, 0, 1000, strict=False, help="Variation within the species."),
        button("randomize", "Randomize", "hou.phm().randomize(kwargs['node'])",
               help="Picks a new seed."),
        flt("flower_scale", "Overall Scale", 1.0, 0.1, 5, strict=True,
            help="Uniform scale of the whole plant. Sizes inside are in metres."),
        hou.SeparatorParmTemplate("sep_lod"),
        int_("petal_rows", "Petal Rows", 20, 2, 64, help="Segments along each petal."),
        int_("petal_cols", "Petal Columns", 12, 2, 48, help="Segments across each petal."),
    ])

    petals = folder("Petals", [
        sub("Arrangement", [
            menu("arrangement", "Arrangement",
                 [("spiral", "Golden Spiral"), ("whorls", "Whorls"), ("rays", "Ray Rows")],
                 d["arrangement"],
                 help="Golden spiral for roses and peonies, whorls for tulips and lilies, "
                      "ray rows for daisies and sunflowers."),
            int_("petal_count", "Petal Count", d["petal_count"], 1, 120,
                 hide_when="{ arrangement != 0 arrangement != spiral }", help="Total petals in the spiral."),
            flt("divergence", "Divergence", d["divergence"], 90, 180,
                hide_when="{ arrangement != 0 arrangement != spiral }",
                help="Angle between consecutive petals. 137.5 is the golden angle."),
            int_("whorls", "Whorls", d.get("whorls", 2), 1, 8, hide_when="{ arrangement != 1 arrangement != whorls }"),
            int_("petals_per_whorl", "Petals per Whorl", d.get("petals_per_whorl", 3), 1, 24,
                 hide_when="{ arrangement != 1 arrangement != whorls }"),
            flt("whorl_offset", "Whorl Offset", d.get("whorl_offset", 60), 0, 180,
                hide_when="{ arrangement != 1 arrangement != whorls }", help="Rotation of each whorl against the one outside it."),
            int_("ray_count", "Rays per Row", d.get("ray_count", 21), 3, 80,
                 hide_when="{ arrangement != 2 arrangement != rays }"),
            int_("ray_rows", "Ray Rows", d.get("ray_rows", 2), 1, 6, hide_when="{ arrangement != 2 arrangement != rays }"),
        ]),
        sub("Head", [
            flt("head_radius", "Head Radius", d["head_radius"], 0.001, 0.05, strict=True,
                help="Radius where the outermost petals attach."),
            flt("head_inner_radius", "Inner Radius", d["head_inner_radius"], 0, 1, strict=True,
                help="Attachment radius of the innermost petals, as a fraction of Head Radius."),
            flt("head_rise", "Rise", d["head_rise"], 0, 0.05, help="How much higher the inner petals attach."),
            ramp("size_ramp", "Size by Layer", d["size_ramp"],
                 help="Petal size from the outermost (left) to the innermost (right) petal."),
        ]),
        sub("Shape", [
            flt("petal_length", "Length", d["petal_length"], 0.001, 0.2, strict=True),
            flt("petal_width", "Width", d["petal_width"], 0.001, 0.2, strict=True),
            ramp("width_ramp", "Width Profile", d["width_ramp"],
                 help="Width along the petal, base (left) to tip (right)."),
            flt("tip_round", "Tip Roundness", d["tip_round"], 0, 1),
            flt("tip_notch", "Tip Notch", d["tip_notch"], 0, 0.5),
            flt("tip_notch_width", "Notch Width", d.get("tip_notch_width", 0.3), 0.01, 1),
            ramp("cup_ramp", "Cup Profile", d["cup_ramp"], help="How much of the cup applies along the petal."),
            flt("edge_roll", "Edge Roll", d["edge_roll"], 0, 2, help="Margins rolling back near the tip, as on roses."),
            flt("ruffle", "Ruffle", d["ruffle"], 0, 0.1),
            flt("ruffle_freq", "Ruffle Frequency", d["ruffle_freq"], 0, 12),
        ]),
        sub("Open Pose", [
            flt("open_angle_outer", "Opening Outer", d["open_angle_outer"], 0, 150,
                help="Angle from the flower axis of the outermost petals when fully open, in degrees."),
            flt("open_angle_inner", "Opening Inner", d["open_angle_inner"], 0, 150),
            ramp("open_ramp", "Opening by Layer", d["open_ramp"],
                 help="Blend from the outer to the inner opening angle, outermost petal on the left."),
            flt("bend_open", "Bend", d["bend_open"], -180, 180, help="Bend along the petal, degrees. Positive bends outward."),
            flt("cup_open", "Cup", d["cup_open"], -90, 270, help="Cross-section curl, degrees. Positive cups toward the center."),
            flt("tip_curl", "Tip Curl", d["tip_curl"], -180, 270),
            flt("tip_curl_start", "Tip Curl Start", d["tip_curl_start"], 0, 0.99),
            flt("open_wrap", "Inner Wrap", d.get("open_wrap", 0.0), 0, 1, strict=True,
                help="Keeps the inner layers wrapped round the axis in the open flower, "
                     "for a cupped center as on garden roses."),
            flt("open_nest", "Inner Nesting", d.get("open_nest", 0.0), 0, 0.9, strict=True,
                help="Pulls the inner layers further in when open."),
        ]),
        sub("Bud Pose", [
            flt("closed_angle_outer", "Closed Outer", d["closed_angle_outer"], -30, 90),
            flt("closed_angle_inner", "Closed Inner", d["closed_angle_inner"], -30, 90),
            flt("bend_closed", "Bend", d["bend_closed"], -180, 180),
            flt("cup_closed", "Cup", d["cup_closed"], -90, 270),
            flt("tip_curl_closed", "Tip Curl", d["tip_curl_closed"], -180, 270),
            flt("bud_wrap", "Wrap", d.get("bud_wrap", 1.0), 0, 1, strict=True,
                help="How much closed petals wrap round the flower axis. At 1 the bud is a set "
                     "of nested shells that cannot cross."),
            flt("bud_nest", "Nesting", d.get("bud_nest", 0.3), 0, 0.9, strict=True,
                help="How much further in the inner petals sit in the bud."),
            flt("bud_length", "Bud Length", d.get("bud_length", 1.0), 0.1, 1, strict=True,
                help="Petal length in the bud as a fraction of the open length. "
                     "Petals grow to full length as they open."),
        ]),
        sub("Bud Shape", [
            flt("bud_shell", "Nested Shells", d.get("bud_shell", 0.0), 0, 1, strict=True,
                help="Lays every closed petal on its own layer of a bud-shaped surface, so "
                     "the bud cannot have crossing petals. Petals peel off their layer as they open. "
                     "At 0 the bud uses the Bud Pose angles only. Turn it above 0 to edit the shell controls below."),
            flt("bud_width", "Bud Width", d.get("bud_width", 0.3), 0.02, 1, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="Widest radius of the bud, as a fraction of Petal Length."),
            flt("bud_height", "Bud Height", d.get("bud_height", 0.8), 0.05, 1.5, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="Height of the bud, as a fraction of Petal Length."),
            flt("bud_fullness", "Widest Point", d.get("bud_fullness", 0.35), 0.02, 0.98, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="Where the bud is widest, from the base (0) to the top (1)."),
            flt("bud_tip", "Tip Roundness", d.get("bud_tip", 0.4), 0, 1,
                disable_when="{ bud_shell == 0 }", help="0 gives a pointed bud, 1 a round one."),
            flt("bud_fill", "Fill", d.get("bud_fill", 0.5), 0, 1,
                disable_when="{ bud_shell == 0 }",
                help="At 1 every petal stretches to the top of its layer, closing the bud; "
                     "at 0 petals keep their own bud length."),
            flt("bud_release", "Release", d.get("bud_release", 0.45), 0.02, 1, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="How much of its opening a petal takes to leave its layer."),
            flt("bud_gap", "Layer Gap", d.get("bud_gap", 0.003), 0, 0.05,
                disable_when="{ bud_shell == 0 }",
                help="Makes each petal's layer this much smaller than the one outside it, so "
                     "petals that attach at the same radius still get their own layer."),
        ]),
        sub("Open Cup", [
            flt("open_hold", "Held Layers", d.get("open_hold", 0.0), 0, 1, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="The inner layers that stay on their nested layer in the open flower, as a "
                     "fraction of all layers. The layers open from the bud into the cup below, "
                     "so a cupped center like a garden rose's cannot cross. 0 releases every petal."),
            flt("open_cup_width", "Cup Width", d.get("open_cup_width", d.get("bud_width", 0.3)), 0.02, 1.5, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="Widest radius of the open cup, as a fraction of Petal Length."),
            flt("open_cup_height", "Cup Height", d.get("open_cup_height", d.get("bud_height", 0.8)), 0.05, 1.5, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="Height of the open cup, as a fraction of Petal Length."),
            flt("open_cup_mouth", "Cup Mouth", d.get("open_cup_mouth", 0.0), 0, 1, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="How open the top of the cup is: 0 stays closed like the bud, 1 is as wide "
                     "as the widest point."),
            flt("open_cup_start", "Cup Start", d.get("open_cup_start", 0.0), 0, 0.95, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="The bloom at which the layers start to open from the bud into the cup."),
            flt("open_cup_end", "Cup End", d.get("open_cup_end", 1.0), 0.05, 1, strict=True,
                disable_when="{ bud_shell == 0 }",
                help="The bloom at which the layers reach the open cup. Below 1 the center opens "
                     "ahead of the outer petals instead of staying a closed ball."),
        ]),
        sub("Variation", [
            flt("jitter_azimuth", "Placement Jitter", d["jitter_azimuth"], 0, 45),
            flt("jitter_size", "Size Jitter", d["jitter_size"], 0, 0.5),
            flt("jitter_angle", "Opening Jitter", d["jitter_angle"], 0, 30),
            flt("jitter_twist", "Twist Jitter", d["jitter_twist"], 0, 45),
        ]),
        sub("Color", [
            color("color_base", "Base", d["color_base"]),
            color("color_tip", "Tip", d["color_tip"]),
            flt("color_gamma", "Gradient Bias", d["color_gamma"], 0.1, 4),
        ]),
    ])

    center = folder("Center", [
        sub("Receptacle", [
            toggle("enable_center", "Center", d["enable_center"], help="Turn on to build the receptacle. Turn it on to edit the controls below."),
            menu("center_type", "Center Type", [("dome", "Dome"), ("disc", "Disc Florets")],
                 d.get("center_type", 0), help="Disc Florets covers the dome with a golden spiral "
                 "of florets, for daisies and sunflowers."),
            flt("center_size", "Size", d["center_size"], 0, 3, help="Receptacle radius as a fraction of Head Radius."),
            flt("center_height", "Height", d["center_height"], 0, 3),
            flt("center_offset", "Offset", d["center_offset"], -1, 1),
            color("center_color", "Color", d["center_color"]),
            color("center_color_inner", "Inner Color", d.get("center_color_inner", (0.45, 0.5, 0.12)),
                  disable_when="{ center_type != 1 center_type != disc }", help="Colour of the unopened florets in the middle."),
            int_("disc_florets", "Florets", d.get("disc_florets", 300), 10, 3000,
                 disable_when="{ center_type != 1 center_type != disc }"),
            flt("floret_size", "Floret Size", d.get("floret_size", 1.0), 0.1, 3,
                disable_when="{ center_type != 1 center_type != disc }"),
        ]),
        sub("Stamens", [
            toggle("enable_stamens", "Stamens", d.get("enable_stamens", 0), help="Turn on to build stamens. Turn it on to edit the controls below."),
            int_("stamen_count", "Count", d.get("stamen_count", 30), 1, 400,
                 disable_when="{ enable_stamens == 0 }"),
            flt("stamen_ring", "Ring", d.get("stamen_ring", 0.8), 0, 2, disable_when="{ enable_stamens == 0 }",
                help="Radius of the stamen ring as a fraction of the receptacle."),
            flt("stamen_length", "Length", d.get("stamen_length", 0.012), 0.001, 0.1,
                disable_when="{ enable_stamens == 0 }"),
            flt("stamen_spread", "Spread", d.get("stamen_spread", 20), -30, 120,
                disable_when="{ enable_stamens == 0 }"),
            flt("stamen_curl", "Curl", d.get("stamen_curl", 30), -180, 180,
                disable_when="{ enable_stamens == 0 }"),
            flt("filament_radius", "Filament Radius", d.get("filament_radius", 0.00025), 0.00002, 0.003,
                disable_when="{ enable_stamens == 0 }"),
            flt("anther_size", "Anther Size", d.get("anther_size", 0.0008), 0.0001, 0.01,
                disable_when="{ enable_stamens == 0 }"),
            color("stamen_color", "Filament Color", d.get("stamen_color", (0.9, 0.85, 0.5)),
                  disable_when="{ enable_stamens == 0 }"),
            color("anther_color", "Anther Color", d.get("anther_color", (0.95, 0.7, 0.1)),
                  disable_when="{ enable_stamens == 0 }"),
        ]),
        sub("Pistil", [
            toggle("enable_pistil", "Pistil", d.get("enable_pistil", 0), help="Turn on to build the pistil. Turn it on to edit the controls below."),
            flt("pistil_length", "Length", d.get("pistil_length", 0.015), 0.001, 0.1,
                disable_when="{ enable_pistil == 0 }"),
            flt("pistil_radius", "Radius", d.get("pistil_radius", 0.0012), 0.0001, 0.01,
                disable_when="{ enable_pistil == 0 }"),
            int_("stigma_lobes", "Stigma Lobes", d.get("stigma_lobes", 3), 1, 8,
                 disable_when="{ enable_pistil == 0 }"),
            flt("stigma_size", "Stigma Size", d.get("stigma_size", 0.0015), 0.0001, 0.01,
                disable_when="{ enable_pistil == 0 }"),
            color("pistil_color", "Color", d.get("pistil_color", (0.75, 0.8, 0.45)),
                  disable_when="{ enable_pistil == 0 }"),
            color("stigma_color", "Stigma Color", d.get("stigma_color", (0.85, 0.85, 0.5)),
                  disable_when="{ enable_pistil == 0 }"),
        ]),
    ])

    sepals = folder("Sepals", [
        toggle("enable_sepals", "Sepals", d.get("enable_sepals", 1), help="Turn on to build sepals. Turn it on to edit the controls below."),
        int_("sepal_count", "Count", d.get("sepal_count", 5), 1, 40, disable_when="{ enable_sepals == 0 }"),
        flt("sepal_length", "Length", d.get("sepal_length", 0.03), 0.001, 0.2, strict=True,
            disable_when="{ enable_sepals == 0 }"),
        flt("sepal_width", "Width", d.get("sepal_width", 0.008), 0.0005, 0.1, strict=True,
            disable_when="{ enable_sepals == 0 }"),
        ramp("sepal_width_ramp", "Width Profile", d.get("sepal_width_ramp", [[0, 0.6], [0.3, 1.0], [1, 0.05]]),
             disable_when="{ enable_sepals == 0 }"),
        flt("sepal_radius", "Attach Radius", d.get("sepal_radius", 1.0), 0, 3, disable_when="{ enable_sepals == 0 }",
            help="Where the sepals attach, as a fraction of Head Radius."),
        flt("sepal_offset", "Rotate", d.get("sepal_offset", 36), 0, 360, disable_when="{ enable_sepals == 0 }"),
        flt("sepal_open_angle", "Open Angle", d.get("sepal_open_angle", 130), -30, 180,
            disable_when="{ enable_sepals == 0 }"),
        flt("sepal_closed_angle", "Closed Angle", d.get("sepal_closed_angle", 8), -30, 180,
            disable_when="{ enable_sepals == 0 }"),
        flt("sepal_bend_open", "Open Bend", d.get("sepal_bend_open", 30), -180, 180,
            disable_when="{ enable_sepals == 0 }"),
        flt("sepal_bend_closed", "Closed Bend", d.get("sepal_bend_closed", -15), -180, 180,
            disable_when="{ enable_sepals == 0 }"),
        flt("sepal_cup_open", "Open Cup", d.get("sepal_cup_open", 30), -90, 270, disable_when="{ enable_sepals == 0 }"),
        flt("sepal_cup_closed", "Closed Cup", d.get("sepal_cup_closed", 80), -90, 270,
            disable_when="{ enable_sepals == 0 }"),
        flt("sepal_settle", "Settle Open Sepals", d.get("sepal_settle", 1), 0, 1, strict=True,
            disable_when="{ enable_sepals == 0 }",
            help="How much the de-intersect pass leaves sepals alone once they have opened. 1 stops them jittering while the petals still move; 0 lets the pass keep pushing them off the petals."),
        flt("sepal_bud_length", "Bud Length", d.get("sepal_bud_length", 1), 0.5, 5, strict=True,
            disable_when="{ enable_sepals == 0 }",
            help="Sepal length at bloom 0 as a multiple of Length; eases to 1 as the sepals open. Above 1 makes bracts that close over the head (daisy)."),
        flt("sepal_bud_width", "Bud Width", d.get("sepal_bud_width", 1), 0.5, 5, strict=True,
            disable_when="{ enable_sepals == 0 }",
            help="Sepal width at bloom 0 as a multiple of Width; eases to 1 as the sepals open."),
        flt("sepal_lead", "Lead", d.get("sepal_lead", 0.35), 0.05, 1, strict=True,
            disable_when="{ enable_sepals == 0 }",
            help="Sepals are fully open when the bloom reaches this value."),
        color("sepal_color", "Color", d.get("sepal_color", (0.12, 0.3, 0.08)), disable_when="{ enable_sepals == 0 }"),
        color("sepal_color_tip", "Tip Color", d.get("sepal_color_tip", (0.2, 0.4, 0.1)),
              disable_when="{ enable_sepals == 0 }"),
    ])

    stem = folder("Stem", [
        toggle("enable_stem", "Stem", 1, help="Turn on to build the stem. Turn it on to edit the controls below."),
        flt("stem_height", "Height", d["stem_height"], 0.01, 2, strict=True),
        flt("stem_radius", "Radius", d["stem_radius"], 0.0005, 0.02, strict=True),
        ramp("stem_radius_ramp", "Radius Profile", d["stem_radius_ramp"]),
        flt("stem_bend", "Bend", d["stem_bend"], -90, 90),
        flt("stem_bend_dir", "Bend Direction", d["stem_bend_dir"], 0, 360),
        flt("head_nod", "Head Nod", d["head_nod"], -90, 120, help="Extra bend near the top, so the head nods."),
        flt("stem_wobble", "Wobble", d["stem_wobble"], 0, 0.2),
        flt("stem_wobble_freq", "Wobble Frequency", d["stem_wobble_freq"], 0, 6),
        int_("stem_segments", "Segments", 40, 4, 200),
        int_("stem_sides", "Sides", 10, 3, 32),
        color("stem_color", "Color", d["stem_color"]),
    ])

    leaves = folder("Leaves", [
        toggle("enable_leaves", "Leaves", d.get("enable_leaves", 1), help="Turn on to build leaves. Turn it on to edit the controls below."),
        sub("Placement", [
            int_("leaf_count", "Count", d.get("leaf_count", 6), 0, 60, disable_when="{ enable_leaves == 0 }"),
            menu("leaf_arrangement", "Arrangement",
                 [("alternate", "Alternate"), ("opposite", "Opposite"), ("whorled", "Whorled (3)"),
                  ("spiral", "Spiral")], d.get("leaf_arrangement", 0), disable_when="{ enable_leaves == 0 }"),
            flt("leaf_start", "Start", d.get("leaf_start", 0.25), 0, 1, disable_when="{ enable_leaves == 0 }",
                help="Lowest leaf, as a fraction of the stem."),
            flt("leaf_end", "End", d.get("leaf_end", 0.75), 0, 1, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_rotate", "Rotate", d.get("leaf_rotate", 0), 0, 360, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_rotate_random", "Random Rotation", d.get("leaf_rotate_random", 0), 0, 180,
                disable_when="{ enable_leaves == 0 }",
                help="Each leaf turns around the stem by a random angle up to this many degrees either way."),
            flt("leaf_grow", "Grow With Bloom", d.get("leaf_grow", 0), 0, 1, disable_when="{ enable_leaves == 0 }",
                help="How much smaller and more folded the leaves start. They reach full size and pose when the bloom ends."),
            flt("leaf_divergence", "Divergence", d.get("leaf_divergence", 180), 0, 360,
                disable_when="{ enable_leaves == 0 }", hide_when="{ leaf_arrangement != 0 leaf_arrangement != alternate }",
                help="Angle between successive leaves for the Alternate arrangement. 180 is exactly opposite sides."),
            ramp("leaf_size_ramp", "Size along Stem", d.get("leaf_size_ramp", [[0, 1.0], [1, 0.7]]),
                 disable_when="{ enable_leaves == 0 }"),
            flt("leaf_jitter", "Jitter", d.get("leaf_jitter", 0.5), 0, 1, disable_when="{ enable_leaves == 0 }"),
        ]),
        sub("Shape", [
            int_("leaflets", "Leaflets", d.get("leaflets", 1), 1, 15, disable_when="{ enable_leaves == 0 }",
                 help="1 for a simple leaf. 3, 5, 7... for a compound leaf with leaflet pairs, as on roses."),
            flt("leaflet_scale", "Leaflet Length", d.get("leaflet_scale", 0.4), 0.05, 1,
                disable_when="{ enable_leaves == 0 } { leaflets < 2 }",
                help="Leaflet length as a fraction of the leaf length."),
            flt("leaflet_angle", "Leaflet Angle", d.get("leaflet_angle", 55), 0, 90,
                disable_when="{ enable_leaves == 0 } { leaflets < 2 }"),
            flt("leaf_length", "Length", d.get("leaf_length", 0.06), 0.001, 0.6, strict=True,
                disable_when="{ enable_leaves == 0 }"),
            flt("leaf_width", "Width", d.get("leaf_width", 0.025), 0.0005, 0.3, strict=True,
                disable_when="{ enable_leaves == 0 }"),
            ramp("leaf_width_ramp", "Width Profile",
                 d.get("leaf_width_ramp", [[0, 0.05], [0.12, 0.1], [0.4, 1.0], [1, 0.0]]),
                 disable_when="{ enable_leaves == 0 }"),
            flt("leaf_serration", "Serration", d.get("leaf_serration", 0.0), 0, 1, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_teeth", "Teeth", d.get("leaf_teeth", 12), 1, 60, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_fold", "Midrib Fold", d.get("leaf_fold", 0.15), -1, 1, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_cup", "Cup", d.get("leaf_cup", 0), -90, 180, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_ruffle", "Ruffle", d.get("leaf_ruffle", 0.01), 0, 0.1, disable_when="{ enable_leaves == 0 }"),
            int_("leaf_rows", "Rows", 16, 2, 64, disable_when="{ enable_leaves == 0 }"),
            int_("leaf_cols", "Columns", 8, 2, 32, disable_when="{ enable_leaves == 0 }"),
        ]),
        sub("Pose", [
            flt("leaf_angle", "Angle", d.get("leaf_angle", 50), 0, 180, disable_when="{ enable_leaves == 0 }",
                help="Angle from the stem, degrees."),
            flt("leaf_bend", "Droop", d.get("leaf_bend", 25), -180, 180, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_tip_curl", "Tip Curl", d.get("leaf_tip_curl", 10), -180, 180, disable_when="{ enable_leaves == 0 }"),
            flt("leaf_twist", "Twist", d.get("leaf_twist", 15), 0, 90, disable_when="{ enable_leaves == 0 }"),
        ]),
        color("leaf_color", "Color", d.get("leaf_color", (0.1, 0.28, 0.07)), disable_when="{ enable_leaves == 0 }"),
        color("leaf_color_tip", "Tip Color", d.get("leaf_color_tip", (0.16, 0.36, 0.1)),
              disable_when="{ enable_leaves == 0 }"),
    ], name="leaves_tab")

    thorns = folder("Thorns", [
        toggle("enable_thorns", "Thorns", d.get("enable_thorns", 0), help="Turn on to build thorns. Turn it on to edit the controls below."),
        int_("thorn_count", "Count", d.get("thorn_count", 25), 0, 400, disable_when="{ enable_thorns == 0 }"),
        flt("thorn_start", "Start", d.get("thorn_start", 0.05), 0, 1, disable_when="{ enable_thorns == 0 }"),
        flt("thorn_end", "End", d.get("thorn_end", 0.8), 0, 1, disable_when="{ enable_thorns == 0 }"),
        flt("thorn_size", "Size", d.get("thorn_size", 0.006), 0.0005, 0.05, disable_when="{ enable_thorns == 0 }"),
        flt("thorn_width", "Base Width", d.get("thorn_width", 0.35), 0.05, 1, disable_when="{ enable_thorns == 0 }"),
        flt("thorn_hook", "Hook", d.get("thorn_hook", 0.4), -1, 2, disable_when="{ enable_thorns == 0 }"),
        flt("thorn_lean", "Lean Down", d.get("thorn_lean", 0.6), -1, 2, disable_when="{ enable_thorns == 0 }"),
        color("thorn_color", "Color", d.get("thorn_color", (0.25, 0.25, 0.08)), disable_when="{ enable_thorns == 0 }"),
        color("thorn_color_tip", "Tip Color", d.get("thorn_color_tip", (0.45, 0.2, 0.1)),
              disable_when="{ enable_thorns == 0 }"),
    ], name="thorns_tab")

    anim = folder("Animation", [
        menu("anim_mode", "Mode", [("slider", "Bloom Slider"), ("time", "Timed Bloom")], 0,
             help="Bloom Slider: set or keyframe Bloom yourself. Timed Bloom: opens between "
                  "Start Frame and Start Frame + Duration."),
        flt("bloom", "Bloom", 1.0, 0, 1, strict=True,
            help="0 is a closed bud, 1 is fully open. In Bloom Slider mode it sets the flower's "
                 "openness directly (keyframe it). In Timed Bloom mode it sets how open the flower "
                 "is when the timed opening ends."),
        flt("bloom_start", "Start Frame", 1, 1, 240, hide_when="{ anim_mode != 1 anim_mode != time }"),
        flt("bloom_duration", "Duration", 72, 1, 480, strict=True, hide_when="{ anim_mode != 1 anim_mode != time }",
            help="Frames from the first petal moving to the last petal settling."),
        flt("stagger", "Layer Stagger", 0.5, 0, 0.95, strict=True,
            help="How much later each inner layer starts. Outer petals always lead."),
        flt("peel", "Peel", 0.3, 0, 0.9, strict=True,
            help="How far the hinge leads the uncurl, for a peeling-open look."),
        flt("overshoot", "Overshoot", 0.0, 0, 0.5, help="Petals swing past their open pose and settle back."),
        flt("open_growth", "Open With Growth", 0.0, 0, 1, strict=True,
            help="0 = hinge leads the uncurl. 1 = opening angle, bend, cup and length run together "
                 "on one eased curve and the tip curl comes in at the end (daisy rays)."),
        toggle("smooth_anim", "Smooth Animation", 0,
               help="Blends the de-intersect result between evenly spaced bloom keys, so petals move "
                    "smoothly from frame to frame instead of jumping when the pass changes its mind. "
                    "Experimental, off by default: it smooths motion but can let petals cross between keys. "
                    "Costs about twice the cook time with De-intersect on."),
        int_("smooth_steps", "Steps", 24, 4, 100, disable_when="{ smooth_anim == 0 }",
             help="Number of bloom keys the pass is solved at. More steps follow the pass more "
                  "closely between keys but cook no faster."),
        sub("Cache", [
            hou.StringParmTemplate("cache_file", "Cache File", 1,
                                   default_value=("$HIP/cache/$OS/flower.$F4.bgeo.sc",),
                                   string_type=hou.stringParmType.FileReference,
                                   file_type=hou.fileType.Geometry),
            button("save_to_disk", "Save to Disk", "hou.phm().save_to_disk(kwargs['node'])",
                   help="Cooks and writes every frame of the bloom to the cache file: Timed Bloom from "
                        "Start Frame to Start Frame + Duration, Bloom Slider over the playbar range. "
                        "Press Esc to cancel."),
            toggle("load_from_disk", "Load from Disk", 0,
                   help="Read the saved frames instead of cooking the flower, for smooth scrubbing. "
                        "Save to Disk again after changing any other parameter."),
        ]),
        sub("De-intersect", [
            toggle("deintersect", "De-intersect Petals", 1,
                   help="Pushes any petal or sepal that passes through a part inside it back out, "
                        "every frame. Turn it on to edit the controls below."),
            int_("deintersect_res", "Resolution", 120, 16, 720, disable_when="{ deintersect == 0 }",
                 help="Cells of the direction buffer from top to bottom. Raise it for many small petals."),
            flt("deintersect_gap", "Gap", 0.0003, 0, 0.005, disable_when="{ deintersect == 0 }",
                help="Clearance kept between layers, in metres. Raise it for petals rendered with thickness."),
            flt("deintersect_reach", "Max Push", 0.5, 0.05, 2, disable_when="{ deintersect == 0 }",
                help="Largest push allowed, as a fraction of the petal length."),
            flt("deintersect_angle", "Max Hinge Angle", d.get("deintersect_angle", 25), 0, 90,
                disable_when="{ deintersect == 0 }",
                help="An overlapping petal first opens further on its hinge, up to this many degrees, "
                     "which keeps its shape. Anything left is pushed out locally."),
            flt("deintersect_center", "Viewpoint Height", d.get("deintersect_center", 0.0), 0, 2,
                disable_when="{ deintersect == 0 }",
                help="Height above the receptacle, in petal lengths, of the point layers are sorted "
                     "from in the open flower. 0 suits cupped flowers; raise it for flat ones like daisies."),
            flt("deintersect_center_bud", "Bud Viewpoint Height", d.get("deintersect_center_bud", d.get("deintersect_center", 0.0)), 0, 2,
                disable_when="{ deintersect == 0 }",
                help="The same height in the closed bud. The viewpoint moves from this to Viewpoint "
                     "Height as the flower opens. Keep it inside the bud."),
            flt("deintersect_center_end", "Viewpoint Settles At", d.get("deintersect_center_end", 1.0), 0.05, 1,
                disable_when="{ deintersect == 0 }",
                help="The bloom value at which the viewpoint reaches Viewpoint Height. Set it to where "
                     "the petals stop moving, so the pass settles with them."),
            flt("deintersect_center_hold", "Viewpoint Holds From", d.get("deintersect_center_hold", 1.0), 0, 1,
                disable_when="{ deintersect == 0 }",
                help="The bloom value from which the viewpoint stops changing. Set it to where the "
                     "petals stop moving, so the pass input is steady once they are."),
            flt("deintersect_shell_fade", "Shell Fade", d.get("deintersect_shell_fade", 0.0), 0, 0.5,
                disable_when="{ deintersect == 0 }",
                help="Blades that have only just left their bud shell take their push in over this much "
                     "of the shell value (0.15 = over shell 0.85 to 1). 0 skips the push only while "
                     "fully on the shell."),
            flt("deintersect_dilate", "Slope Limit", d.get("deintersect_dilate", 0.0), 0, 5,
                disable_when="{ deintersect == 0 }",
                help="Caps how steeply the depth buffer can change, in petal-width units per cell, so a "
                     "blade sliding over an edge is pushed gradually. 0 = off (cheaper)."),
            flt("deintersect_cone", "Cone Lookup", d.get("deintersect_cone", 0.0), 0, 5,
                disable_when="{ deintersect == 0 }",
                help="Looks up the depth buffer through a cone: a cell counts at its depth minus this "
                     "much (petal-width units) per cell of distance, so a blade sliding over an edge "
                     "sees the depth change gradually. 0 = off (plain 3x3 maximum)."),
            int_("deintersect_smooth", "Smoothing", 6, 0, 16, disable_when="{ deintersect == 0 }",
                 help="Radius, in petal grid cells, over which each push fades out, "
                      "so pushed petals stay smooth."),
        ]),
    ])

    for f in (flower, petals, center, sepals, stem, leaves, thorns, anim):
        g.append(f)
    return g
