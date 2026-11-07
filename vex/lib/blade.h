// Shared builder for flat organs: petals, sepals and leaves.
// The build script inlines this file wherever a snippet says #include "blade.h".
//
// A blade grows from `base`. Its spine lies in the plane of the local axis Y and
// the outward direction R; its angle from Y is alpha + bend * s + tip curl near
// the tip. s runs 0 (base) to 1 (tip) along the spine, t runs -1 to 1 across.

// Wrangle snippets cannot declare structs, so the shape travels in a float
// array addressed by these names. Angles are in radians.
#define B_L        0   // length
#define B_HW       1   // half width
#define B_ALPHA    2   // angle of the spine from the axis at the base
#define B_BEND     3   // bend along the whole length
#define B_TIPCURL  4   // extra bend near the tip
#define B_TCS      5   // where the tip curl starts, 0 to 1
#define B_CUP      6   // cross-section curl
#define B_ROLL     7   // margins rolling back near the tip
#define B_FOLD     8   // V fold along the midrib
#define B_TROUND   9   // round tip
#define B_NOTCH   10   // notched tip
#define B_NOTW    11   // notch width
#define B_SERR    12   // serrated margin depth
#define B_SERRF   13   // number of teeth
#define B_RUFFLE  14   // edge ruffle
#define B_RFREQ   15   // ruffle frequency
#define B_TWIST   16   // twist along the length
#define B_SEED    17
#define B_WRAP    18   // 0 to 1: bend the cross-section round the flower axis (nested bud shells)
#define B_NEST    19   // 0 to 1: pull the whole blade toward the flower axis
#define B_SHELL   20   // 0 to 1: lay the blade on its own nested bud shell (see bud_profile)
#define B_SR0     21   // bud shell: base radius of the full-size shell
#define B_SRB     22   // bud shell: widest radius of the full-size shell
#define B_SHB     23   // bud shell: height of the full-size shell
#define B_SFULL   24   // bud shell: where it is widest, 0 (base) to 1 (top)
#define B_STIP    25   // bud shell: 0 pointed tip, 1 round tip
#define B_SD      26   // bud shell: this blade's shell as a scale of the full-size one
#define B_SFILL   27   // bud shell: 0 keeps the blade's length, 1 stretches it to the top of its shell
#define B_SYO     28   // bud shell: height on the axis that every shell is scaled about
#define B_SCLOSE  29   // bud shell: 1 closes the top (bud), less leaves an open cup
#define B_N       30

function float[] blade_defaults() {
    float sh[];
    resize(sh, B_N);
    sh[B_TCS] = 0.7;
    sh[B_NOTW] = 0.3;
    sh[B_SCLOSE] = 1;
    return sh;
}

// Radius of the full-size bud shell at v, 0 (base) to 1 (top), round the flower
// axis. A blade's shell is this shell scaled about one point O on the axis
// (B_SYO). The region inside the curve is convex and holds O, so a smaller shell
// always lies strictly inside a larger one: shells never cross, and the space
// between two shells grows with the distance from O. Closure below 1 leaves the
// top open (a cup); the curve stays concave for any closure, so it nests too.
float bud_profile(float v; float r0; float rb; float full; float tip; float close) {
    float f = clamp(full, 0.02, 0.98);
    float g = sin(PI * 0.5 * clamp(v / f, 0, 1));
    float w = clamp((v - f) / (1 - f), 0, 1);
    return lerp(r0, rb, g) * pow(max(0, 1 - clamp(close, 0, 1) * w * w), lerp(1.0, 0.5, clamp(tip, 0, 1)));
}

// How far the shells have opened from the bud into the Open Cup at global bloom
// g: they leave the bud at Cup Start and arrive at Cup End, so the center can
// open ahead of the rest of the bloom. Shapes and scales of every shell use this
// one value at a frame, so they stay nested.
float cup_progress(float g) {
    float t1 = clamp(chf("../open_cup_end"), 0.05, 1);
    return smooth(min(chf("../open_cup_start"), t1 - 0.05), t1, g);
}

// The shell shape at global bloom g: the bud opens into the Open Cup, whose base
// radius is r0open. Every shell uses the same shape at a given frame, so they
// stay nested while it opens.
function void shell_shape(float sh[]; float g; float r0open) {
    float pl = chf("../petal_length");
    float e = cup_progress(g);
    sh[B_SR0]    = lerp(chf("../head_radius"), r0open, e);
    sh[B_SRB]    = lerp(chf("../bud_width"), chf("../open_cup_width"), e) * pl;
    sh[B_SHB]    = lerp(chf("../bud_height"), chf("../open_cup_height"), e) * pl;
    sh[B_SFULL]  = chf("../bud_fullness");
    sh[B_STIP]   = chf("../bud_tip");
    sh[B_SFILL]  = chf("../bud_fill");
    sh[B_SCLOSE] = 1 - clamp(chf("../open_cup_mouth"), 0, 1) * e;
}

// Creates the blade's points and quads. Returns the new primitive numbers.
function int[] build_blade(vector base; vector R; vector Y; float sh[]; int nu; int nv;
                  string wramp; string cramp; vector col0; vector col1; float gam) {
    int K = 64;
    vector sp[];
    float sa[];
    resize(sp, K + 1);
    resize(sa, K + 1);
    vector cur = base;
    for (int k = 0; k <= K; k++) {
        float s = k / float(K);
        float w = smooth(sh[B_TCS], 1, s);
        float ang = sh[B_ALPHA] + sh[B_BEND] * s + sh[B_TIPCURL] * w * w;
        sa[k] = ang;
        sp[k] = cur;
        cur += (sin(ang) * R + cos(ang) * Y) * (sh[B_L] / K);
    }
    vector T = normalize(cross(R, Y));

    // Bud shell: the blade's meridian runs up its own shell from the base, sampled
    // evenly in v and measured by arc length (only for blades in head space).
    int KS = 96;
    float shr[], shy[], sha[];
    float slen = 0;
    if (sh[B_SHELL] > 0) {
        float sc = sh[B_SD];
        for (int k = 0; k <= KS; k++) {
            float v = k / float(KS);
            float pr = bud_profile(v, sh[B_SR0], sh[B_SRB], sh[B_SFULL], sh[B_STIP], sh[B_SCLOSE]);
            if (k > 0 && pr < 0.03 * sh[B_SRB]) break;
            float r = sc * pr, y = (1 - sc) * sh[B_SYO] + sc * v * sh[B_SHB];
            if (k > 0) slen += sqrt(pow(r - shr[-1], 2) + pow(y - shy[-1], 2));
            append(shr, r);
            append(shy, y);
            append(sha, slen);
        }
    }
    float sfit = lerp(min(sh[B_L], slen), slen, sh[B_SFILL]) * 0.98;

    int ids[];
    for (int i = 0; i <= nu; i++) {
        float s = i / float(nu);
        for (int j = 0; j <= nv; j++) {
            float t  = j / float(nv) * 2 - 1;
            float at = abs(t);
            // Tip outline: a notch shortens the middle rows. se = s - cut * s^p stays
            // increasing in s (no fold) when p <= 1 / cut, and p = 3 keeps a small cut
            // near the tip. A round tip narrows the width instead (below), so rows
            // stay evenly spaced and no long thin polygons form along the margins.
            float tc = clamp(sh[B_NOTCH] * pow(max(0, 1 - at / max(1e-3, sh[B_NOTW])), 2), 0, 0.98);
            float se = s - tc * pow(s, min(3, 1 / max(tc, 1e-3)));

            float x  = se * K;
            int   k0 = min(int(floor(x)), K - 1);
            float fr = x - k0;
            vector C = lerp(sp[k0], sp[k0 + 1], fr);
            float ang = lerp(sa[k0], sa[k0 + 1], fr);
            vector nin = -cos(ang) * R + sin(ang) * Y;

            float tw = sh[B_TWIST] * se;
            vector Tt = T * cos(tw) + nin * sin(tw);
            vector Nt = nin * cos(tw) - T * sin(tw);

            float hw = sh[B_HW] * chramp(wramp, se);
            float tr = clamp(sh[B_TROUND], 0, 1);
            float rtip = tr > 0 && se > 1 - tr ? sqrt(max(0, 1 - pow((se - 1 + tr) / tr, 2))) : 1;
            float hwf = hw;     // before the tip is rounded, for the bud shell
            if (sh[B_SERR] > 0) {
                float tooth = frac(se * sh[B_SERRF]);
                hw *= 1 - sh[B_SERR] * tooth * smooth(0.1, 0.3, se);
            }
            // The round tip trims the full-width cross-section (te), so the tip keeps the
            // curvature of the rest of the blade instead of curling into a tube.
            float te = t * rtip, ae = abs(te);
            float cup = sh[B_CUP] * (cramp != "" ? chramp(cramp, se) : 1.0);
            if (sh[B_WRAP] > 0) {
                // An arc whose radius is the spine's distance from the axis is centred on
                // the axis, so blades at different distances form nested shells.
                float rho = max(1e-5, length(set(C.x, 0, C.z)));
                cup = lerp(cup, min(hw / rho, 2.9), sh[B_WRAP]);
            }
            float xs, ys;
            if (abs(cup) < 1e-4) {
                xs = hw * te;
                ys = 0;
            } else {
                xs = hw / cup * sin(cup * te);
                ys = hw / cup * (1 - cos(cup * te));
            }
            ys += sh[B_FOLD] * hw * ae;
            ys -= sh[B_ROLL] * hw * pow(smooth(0.4, 1, ae), 2) * smooth(0.2, 1, se);
            float nz = noise(set(se * sh[B_RFREQ], te * sh[B_RFREQ] * 0.5, sh[B_SEED])) * 2 - 1;
            ys += sh[B_RUFFLE] * sh[B_L] * ae * ae * pow(se, 1.5) * nz;

            vector P = C + Tt * xs + Nt * ys;
            P.x *= 1 - sh[B_NEST];
            P.z *= 1 - sh[B_NEST];
            vector nout = -Nt;
            if (len(sha) > 1) {
                // The same point on the blade's bud shell: arc length along the meridian
                // gives the height, the half width (as arc length round the axis) the angle.
                float a = se * sfit;
                int m = 0;
                while (m < len(sha) - 2 && sha[m + 1] < a) m++;
                float u = clamp((a - sha[m]) / max(1e-9, sha[m + 1] - sha[m]), 0, 1);
                float r = lerp(shr[m], shr[m + 1], u);
                // Compress (not clip) a petal wider than 2.8 rad each side, so columns stay
                // evenly spaced and no facet sags further in than the gap between shells.
                // A petal tip that wraps almost all the way round stays square: a round
                // tip would pull a full ring into one point across the top of the shell.
                float rw = max(r, 1e-6);
                float th = t * min(hwf * lerp(rtip, 1, smooth(0.5, 1, hwf / (2.8 * rw))) / rw, 2.8);
                vector rad = cos(th) * R + sin(th) * T;
                vector Ps = rad * r + Y * lerp(shy[m], shy[m + 1], u);
                // The tip peels off first and the base last, so the base, where the
                // de-intersect pass cannot push, stays nested on its shell the longest.
                float ws = smooth(0, 1, 2 * sh[B_SHELL] - se);
                P = lerp(P, Ps, ws);
                nout = normalize(lerp(nout, rad, ws));
            }
            int pt = addpoint(0, P);
            setpointattrib(0, "gi", pt, i);
            setpointattrib(0, "gj", pt, j);
            setpointattrib(0, "gcols", pt, nv + 1);
            setpointattrib(0, "uv", pt, set(t * 0.5 + 0.5, se, 0));
            setpointattrib(0, "blade_s", pt, se);
            setpointattrib(0, "blade_t", pt, t);
            setpointattrib(0, "nout", pt, nout);   // away from the inside, used by the de-intersect pass
            setpointattrib(0, "Cd", pt, lerp(col0, col1, pow(se, gam)));
            append(ids, pt);
        }
    }

    int prims[];
    int row = nv + 1;
    for (int i = 0; i < nu; i++) {
        for (int j = 0; j < nv; j++) {
            int pr = addprim(0, "poly", ids[i * row + j], ids[i * row + j + 1],
                             ids[(i + 1) * row + j + 1], ids[(i + 1) * row + j]);
            append(prims, pr);
        }
    }
    return prims;
}

// A tapered tube along a polyline, for filaments, thorns and pistils.
// r0 and r1 are the radii at the start and end.
function int[] build_tube(vector C[]; float r0; float r1; int sides; vector col0; vector col1) {
    int n = len(C);
    int ids[];
    vector nprev = {0, 0, 0};
    for (int k = 0; k < n; k++) {
        vector d = k < n - 1 ? C[k + 1] - C[k] : C[k] - C[k - 1];
        vector tg = normalize(d);
        vector nn;
        if (k == 0) {
            nn = abs(tg.y) < 0.9 ? normalize(cross(tg, {0, 1, 0})) : normalize(cross(tg, {1, 0, 0}));
        } else {
            nn = normalize(cross(tg, cross(nprev, tg)));
        }
        nprev = nn;
        vector bn = cross(tg, nn);
        float u = k / float(max(1, n - 1));
        float r = lerp(r0, r1, u);
        for (int j = 0; j < sides; j++) {
            float ph = 2 * PI * j / sides;
            int pt = addpoint(0, C[k] + r * (cos(ph) * nn + sin(ph) * bn));
            setpointattrib(0, "Cd", pt, lerp(col0, col1, u));
            setpointattrib(0, "uv", pt, set(j / float(sides), u, 0));
            append(ids, pt);
        }
    }
    int prims[];
    for (int k = 0; k < n - 1; k++) {
        for (int j = 0; j < sides; j++) {
            int j1 = (j + 1) % sides;
            append(prims, addprim(0, "poly", ids[k * sides + j], ids[k * sides + j1],
                                  ids[(k + 1) * sides + j1], ids[(k + 1) * sides + j]));
        }
    }
    return prims;
}

// A closed ellipsoid, for anthers, stigmas and buds of florets.
function int[] build_blob(vector c; vector ax; float rad; float elong; int sides; vector col) {
    vector a = normalize(ax);
    vector u = abs(a.y) < 0.9 ? normalize(cross(a, {0, 1, 0})) : normalize(cross(a, {1, 0, 0}));
    vector v = cross(a, u);
    int lat = max(3, sides / 2);
    int ids[];
    for (int i = 0; i <= lat; i++) {
        float th = PI * i / lat;
        for (int j = 0; j < sides; j++) {
            float ph = 2 * PI * j / sides;
            vector P = c + a * (rad * elong * cos(th)) + rad * sin(th) * (cos(ph) * u + sin(ph) * v);
            int pt = addpoint(0, P);
            setpointattrib(0, "Cd", pt, col);
            setpointattrib(0, "uv", pt, set(j / float(sides), i / float(lat), 0));
            append(ids, pt);
        }
    }
    int prims[];
    for (int i = 0; i < lat; i++) {
        for (int j = 0; j < sides; j++) {
            int j1 = (j + 1) % sides;
            append(prims, addprim(0, "poly", ids[i * sides + j], ids[(i + 1) * sides + j],
                                  ids[(i + 1) * sides + j1], ids[i * sides + j1]));
        }
    }
    return prims;
}
