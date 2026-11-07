// Shared timing. The build script inlines this file wherever a snippet says
// #include "anim.h".

// Global bloom progress, 0 (bud) to 1 (open): the Bloom slider, or the frame
// inside the timed window. Pass @Frame: functions cannot read it themselves.
// A wrangle with its own spare int parm g_override = 1 uses its g_fixed instead
// (the Smooth Animation key copies); nodes without the parm read 0.
float bloom_progress(float frame) {
    float g;
    if (chi("g_override") == 1) {
        return clamp(chf("g_fixed"), 0, 1);
    } else if (chi("../anim_mode") == 0) {
        g = chf("../bloom");
    } else {
        g = clamp((frame - chf("../bloom_start")) / max(1e-3, chf("../bloom_duration")), 0, 1)
            * chf("../bloom");
    }
    return clamp(g, 0, 1);
}

// Progress of a petal layer: outer layers (layerf 0) start first and every
// layer runs the same length of time, so outer petals always lead.
float layer_progress(float g; float layerf) {
    float st = clamp(chf("../stagger"), 0, 0.95);
    return clamp((g - st * layerf) / (1 - st), 0, 1);
}
