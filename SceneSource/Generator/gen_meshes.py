"""v2 meshes: 3-ring terrain, instanced tree/rock prototypes, outcrops, pad, rings, guide, glider."""
import numpy as np, json
from scipy.spatial import cKDTree
import scene_common as S

rng = np.random.default_rng(S.SEED)

PALETTE = {
    "grass_meadow": [(156, 198, 70), (166, 204, 76), (148, 192, 66), (176, 208, 84)],
    "grass_light":  [(192, 210, 92), (202, 206, 100)],
    "grass_deep":   [(126, 182, 66), (116, 172, 62)],
    "grass_top":    [(132, 186, 70), (122, 178, 64), (142, 192, 74)],
    "grass_far":    [(150, 182, 98), (138, 172, 92)],
    "cliff_light":  [(224, 148, 82), (214, 138, 76)],
    "cliff_mid":    [(200, 116, 62), (190, 106, 58)],
    "cliff_red":    [(176, 92, 54), (166, 86, 52)],
    "cliff_dark":   [(140, 74, 46), (128, 68, 44)],
    "rock_far":     [(178, 132, 112), (162, 120, 106)],
    "tree_green":   [(84, 160, 62), (98, 174, 68), (72, 146, 56), (110, 182, 72)],
    "tree_yellow":  [(198, 178, 80), (208, 190, 92), (182, 162, 70)],
    "tree_dark":    [(62, 130, 58)],
    "trunk":        [(112, 72, 42)],
    "rock":         [(194, 112, 66), (176, 100, 60), (156, 90, 56)],
    "pad":          [(178, 178, 176), (150, 150, 150)],
    "pad_mark":     [(216, 62, 56)],
    "ring":         [(252, 200, 60), (250, 150, 44)],
    "guide":        [(232, 60, 200)],
    "glider_body":  [(238, 238, 236)],
    "glider_fin":   [(52, 86, 226)],
    "glider_red":   [(220, 60, 56)],
    "glider_green": [(70, 190, 110)],
    "glider_pod":   [(246, 130, 40)],
}
PAL_LIST, PAL_INDEX = [], {}
for k, cols in PALETTE.items():
    PAL_INDEX[k] = list(range(len(PAL_LIST), len(PAL_LIST) + len(cols)))
    PAL_LIST += cols
assert len(PAL_LIST) <= 64, len(PAL_LIST)


def pick(name, n=None, r=rng):
    ids = PAL_INDEX[name]
    if n is None:
        return ids[r.integers(len(ids))]
    return np.array(ids)[r.integers(len(ids), size=n)]


class Mesh:
    def __init__(self):
        self.tris = []; self.pal = []

    def tri(self, a, b, c, p):
        self.tris.append(np.array([a, b, c], float)); self.pal.append(p)

    def quad(self, a, b, c, d, p):
        self.tri(a, b, c, p); self.tri(a, c, d, p)

    def arrays(self):
        return np.array(self.tris, np.float32).reshape(-1, 3, 3), np.array(self.pal, np.int32)

# ---------------------------------------------------------------- primitives

def cone(m, base_z, radius, h, sides, p, rot=0.0):
    ang = rot + np.arange(sides) * 2 * np.pi / sides
    ring = np.stack([radius * np.cos(ang), radius * np.sin(ang), np.full(sides, base_z)], 1)
    tip = np.array([0, 0, base_z + h]); c = np.array([0, 0, base_z])
    for i in range(sides):
        a, b = ring[i], ring[(i + 1) % sides]
        m.tri(a, b, tip, p); m.tri(b, a, c, p)


def prism(m, z0, z1, radius, sides, p, rot=0.0):
    ang = rot + np.arange(sides) * 2 * np.pi / sides
    lo = np.stack([radius * np.cos(ang), radius * np.sin(ang), np.full(sides, z0)], 1)
    hi = lo.copy(); hi[:, 2] = z1
    for i in range(sides):
        j = (i + 1) % sides
        m.quad(lo[i], lo[j], hi[j], hi[i], p)


def pine_proto(kind, fam):
    """Unit-scale pine prototypes (height ~ 7.3 m at scale 1)."""
    m = Mesh(); r = np.random.default_rng(hash((kind, fam)) % 1000)
    cols = PAL_INDEX[fam]
    if kind == "A":
        prism(m, -1.0, 1.6, 0.32, 6, PAL_INDEX["trunk"][0])
        tiers = [(1.2, 2.5, 3.3), (2.9, 2.0, 2.9), (4.5, 1.4, 2.8)]; sides = 7
    elif kind == "B":   # slender, 4 tiers
        prism(m, -1.0, 1.4, 0.28, 6, PAL_INDEX["trunk"][0])
        tiers = [(1.0, 1.8, 2.8), (2.6, 1.55, 2.6), (4.1, 1.2, 2.5), (5.5, 0.85, 2.6)]; sides = 7
    elif kind == "C":   # squat, 2 tiers
        prism(m, -1.0, 1.2, 0.36, 6, PAL_INDEX["trunk"][0])
        tiers = [(0.9, 2.8, 3.2), (2.6, 2.0, 3.0)]; sides = 7
    else:               # far LOD: one cone + stub
        prism(m, -1.0, 1.0, 0.4, 4, PAL_INDEX["trunk"][0])
        tiers = [(0.9, 2.3, 6.2)]; sides = 5
    for k, (bz, rad, h) in enumerate(tiers):
        cone(m, bz, rad, h, sides, cols[(k + (fam == "tree_yellow")) % len(cols)], k * 0.45)
    return m


def rock_proto(seed):
    r = np.random.default_rng(seed); m = Mesh()
    t = (1 + 5 ** 0.5) / 2
    V = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    V *= r.uniform(0.72, 1.22, (12, 1))
    F = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6],
         [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10],
         [8, 6, 7], [9, 8, 1]]
    for k, f in enumerate(F):
        a, b, c = V[f[0]], V[f[1]], V[f[2]]
        n = np.cross(b - a, c - a)
        if n @ (a + b + c) < 0:
            b, c = c, b
        m.tri(a, b, c, PAL_INDEX["rock"][k % 3])
    return m


def torus(R, rt, nu, nv, p):
    m = Mesh()
    u = np.arange(nu) * 2 * np.pi / nu; v = np.arange(nv) * 2 * np.pi / nv
    def P(i, j):
        a, b = u[i % nu], v[j % nv]
        return np.array([rt * np.sin(b), (R + rt * np.cos(b)) * np.cos(a), (R + rt * np.cos(b)) * np.sin(a)])
    for i in range(nu):
        for j in range(nv):
            m.quad(P(i, j), P(i, j + 1), P(i + 1, j + 1), P(i + 1, j), p[(i // 2) % len(p)])
    return m


def glider():
    m = Mesh()
    body, fin = PAL_INDEX["glider_body"][0], PAL_INDEX["glider_fin"][0]
    red, green, pod = PAL_INDEX["glider_red"][0], PAL_INDEX["glider_green"][0], PAL_INDEX["glider_pod"][0]
    half = S.GLIDER_HALF_SPAN; up = np.array([0, 0, 1.0])
    for sgn in (1, -1):
        LEr, TEr = np.array([0.55, 0, 0.0]), np.array([-0.55, 0, 0.0])
        LEt, TEt = np.array([-0.35, sgn * half, 0.06]), np.array([-0.80, sgn * half, 0.06])
        th_r, th_t = 0.10, 0.04
        tu = [LEr + up * th_r, TEr + up * th_r * 0.3, TEt + up * th_t * 0.3, LEt + up * th_t]
        bo = [LEr - up * th_r * 0.6, TEr, TEt, LEt - up * th_t * 0.6]
        def q(a, b, c, d, p):
            if sgn > 0: m.quad(a, b, c, d, p)
            else: m.quad(d, c, b, a, p)
        q(tu[0], tu[3], tu[2], tu[1], body); q(bo[0], bo[1], bo[2], bo[3], body)
        q(tu[0], bo[0], bo[3], tu[3], body); q(tu[1], tu[2], bo[2], bo[1], body); q(tu[3], bo[3], bo[2], tu[2], body)
        e = np.array([0, 0, 0.012])
        for (f0, f1, col) in ((0.15, 0.55, green), (0.55, 0.98, red)):
            a = TEr + (TEt - TEr) * f0; b = TEr + (TEt - TEr) * f1
            a2 = a + np.array([0.28, 0, 0]); b2 = b + np.array([0.28, 0, 0])
            a = a + up * (th_r * 0.3 * (1 - f0) + th_t * 0.3 * f0) + e
            b = b + up * (th_r * 0.3 * (1 - f1) + th_t * 0.3 * f1) + e
            a2 = a2 + up * 0.08 * (1 - f0) + e; b2 = b2 + up * 0.08 * (1 - f1) + e
            q(a, a2, b2, b, col)
        base_f, base_b = LEt + np.array([0.05, 0, 0]), TEt + np.array([-0.02, 0, 0])
        top_b = base_b + np.array([0.0, sgn * 0.08, 0.75]); top_f = top_b + np.array([0.28, 0, 0])
        o = np.array([0, sgn * 0.02, 0])
        q(base_f, base_b, top_b, top_f, fin); q(base_f + o, top_f + o, top_b + o, base_b + o, fin)
    c = np.array([0.05, 0, 0.12]); r_ = 0.28
    pts = [c + [r_ * 1.6, 0, 0], c + [0, r_, 0], c + [-r_ * 1.4, 0, 0], c + [0, -r_, 0]]
    top, bot = c + [0, 0, r_], c + [0, 0, -r_ * 0.6]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        m.tri(a, b, top, pod); m.tri(b, a, bot, pod)
    return m

# ---------------------------------------------------------------- terrain

def grid_tris(x0, x1, y0, y1, cell, jitter, hole=None, skirt=0.0):
    nx = int(round((x1 - x0) / cell)) + 1; ny = int(round((y1 - y0) / cell)) + 1
    gx = x0 + np.arange(nx) * cell; gy = y0 + np.arange(ny) * cell
    X, Y = np.meshgrid(gx, gy, indexing="xy")
    if jitter:
        J = rng.uniform(-jitter, jitter, (2, ny, nx)) * cell
        J[:, :, 0] = J[:, :, -1] = 0; J[:, 0, :] = J[:, -1, :] = 0
        if hole is not None:   # no jitter on hole border
            hb = ((np.abs(X - hole[0]) < 1e-6) | (np.abs(X - hole[1]) < 1e-6)) & (Y >= hole[2] - 1e-6) & (Y <= hole[3] + 1e-6)
            hb |= ((np.abs(Y - hole[2]) < 1e-6) | (np.abs(Y - hole[3]) < 1e-6)) & (X >= hole[0] - 1e-6) & (X <= hole[1] + 1e-6)
            J[:, hb] = 0
        X = X + J[0]; Y = Y + J[1]
    Z = S.height(X, Y)
    V = np.stack([X, Y, Z], -1)
    a = V[:-1, :-1]; b = V[:-1, 1:]; c = V[1:, 1:]; d = V[1:, :-1]
    I, Jx = np.meshgrid(np.arange(nx - 1), np.arange(ny - 1), indexing="xy")
    alt = ((I + Jx) % 2 == 0)
    t1 = np.where(alt[..., None, None], np.stack([a, b, c], -2), np.stack([a, b, d], -2))
    t2 = np.where(alt[..., None, None], np.stack([a, c, d], -2), np.stack([b, c, d], -2))
    keep = np.ones(alt.shape, bool)
    if hole is not None:
        cx = (gx[:-1] + gx[1:])[None, :] / 2 + 0 * gy[:-1, None]
        cy = (gy[:-1] + gy[1:])[:, None] / 2 + 0 * gx[None, :-1]
        keep = ~((cx > hole[0]) & (cx < hole[1]) & (cy > hole[2]) & (cy < hole[3]))
    T = np.concatenate([t1[keep], t2[keep]])
    if hole is not None and skirt > 0:   # inner skirt along the hole border (drops below the inner mesh)
        hx0, hx1, hy0, hy1 = hole
        i0 = int(round((hx0 - x0) / cell)); i1 = int(round((hx1 - x0) / cell))
        j0 = int(round((hy0 - y0) / cell)); j1 = int(round((hy1 - y0) / cell))
        lines = [V[j0, i0:i1 + 1], V[j0:j1 + 1, i1], V[j1, i0:i1 + 1][::-1], V[j0:j1 + 1, i0][::-1]]
        sk = []
        for line in lines:
            for i in range(len(line) - 1):
                p, q = line[i], line[i + 1]
                sk += [[p, q, q - [0, 0, skirt]], [p, q - [0, 0, skirt], p - [0, 0, skirt]]]
        T = np.concatenate([T, np.array(sk)])
    if skirt > 0 and hole is None:   # vertical skirt along the outer border (hides seams)
        border = [V[0, :], V[:, -1], V[-1, ::-1], V[::-1, 0]]
        sk = []
        for line in border:
            for i in range(len(line) - 1):
                p, q = line[i], line[i + 1]
                pd, qd = p - [0, 0, skirt], q - [0, 0, skirt]
                sk += [[p, pd, qd], [p, qd, q]]
        T = np.concatenate([T, np.array(sk)])
    return T.astype(np.float32)


def color_terrain(T, layer):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    n[n[:, 2] < 0] *= -1
    cx, cy, cz = T[:, :, 0].mean(1), T[:, :, 1].mean(1), T[:, :, 2].mean(1)
    nz = n[:, 2]; pal = np.zeros(len(T), np.int32)
    steep = nz < 0.74
    if layer == "far":
        rockm = steep | (cz > 380)
        pal[rockm] = pick("rock_far", int(rockm.sum())); pal[~rockm] = pick("grass_far", int((~rockm).sum()))
        return pal
    # cliff strata: lit/back-lit orange-brown layers, darker towards the cliff foot and on overhang-ish faces
    seq = np.array(["cliff_light", "cliff_mid", "cliff_red", "cliff_mid", "cliff_light", "cliff_dark", "cliff_mid"])
    band = np.floor((cz + 6 * S.fbm(cx, cy, 45, 2, 99)) / 9.0).astype(int) % len(seq)
    names = seq[band]
    names = np.where(steep & (nz < 0.32) & (names == "cliff_light"), "cliff_mid", names)
    names = np.where(steep & (nz < 0.25), np.where(names == "cliff_mid", "cliff_red", names), names)
    for nm in np.unique(names[steep]):
        m = steep & (names == nm); pal[m] = pick(str(nm), int(m.sum()))
    gr = ~steep
    if layer == "near":
        far_m = gr & (cz > 300)
        pal[gr] = pick("grass_far", int(gr.sum()))
        nm2 = gr & (S.fbm(cx, cy, 400, 2, 5) > 0.1) & ~far_m
        pal[nm2] = pick("grass_meadow", int(nm2.sum()))
        return pal
    peak_r = np.hypot(cx - S.PEAK_C[0], cy - S.PEAK_C[1])
    high = gr & (cz > 62) & (peak_r > 200)
    pal[gr] = pick("grass_meadow", int(gr.sum()))
    pal[high] = pick("grass_top", int(high.sum()))
    nf = S.fbm(cx, cy, 75, 3, 55)
    light = gr & (nf > 0.36); deep = gr & (nf < -0.42)
    pal[light] = pick("grass_light", int(light.sum())); pal[deep] = pick("grass_deep", int(deep.sum()))
    return pal

# ---------------------------------------------------------------- scatter

PATH3 = cKDTree(S.PATH_P[::4])


def clear_of_route(c, R, margin=27.0):
    d, _ = PATH3.query(c)
    return d - R > margin


def scatter_trees():
    inst = []
    # play area: groves + sparse + lone trees
    step = 6.5
    g = np.arange(4, S.MAP - 4, step)
    X, Y = np.meshgrid(g, g); X = X.ravel() + rng.uniform(-2.5, 2.5, X.size); Y = Y.ravel() + rng.uniform(-2.5, 2.5, Y.size)
    grove = S.smoothstep(0.22, 0.55, S.fbm(X, Y, 150, 3, 201))
    sparse = 0.035 + 0.05 * S.smoothstep(0.0, 0.4, S.fbm(X, Y, 300, 2, 202))
    dens = np.maximum(grove * 0.85, sparse)
    keep = rng.random(X.size) < dens
    X, Y = X[keep], Y[keep]
    nz = S.terrain_normal(X, Y)[:, 2]; Z = S.height(X, Y)
    ok = nz > 0.88
    X, Y, Z = X[ok], Y[ok], Z[ok]
    yel = S.fbm(X, Y, 180, 2, 205) > 0.12
    for x, y, z, yl in zip(X, Y, Z, yel):
        kind = rng.choice(["A", "B", "C"], p=[0.5, 0.3, 0.2])
        sc = rng.uniform(1.15, 2.3) * (1.1 if kind == "B" else 1.0)
        hgt = {"A": 7.3, "B": 8.1, "C": 5.8}[kind] * sc
        c = np.array([x, y, z + hgt * 0.5])
        if not clear_of_route(c, hgt * 0.55):
            continue
        if np.hypot(x - S.START_C[0], y - S.START_C[1]) < 30:
            continue
        fam = "Y" if (yl and rng.random() < 0.75) or rng.random() < 0.08 else "G"
        inst.append(dict(proto=f"SM_Pine{kind}_{fam}", pos=[x, y, z], yaw=float(rng.uniform(0, 360)),
                         scale=[sc, sc, sc * rng.uniform(0.92, 1.1)], layer="play"))
    # near ring: sparse far-LOD clumps
    near = []
    g = np.arange(S.NEAR_BOX[0], S.NEAR_BOX[1], 22.0)
    X, Y = np.meshgrid(g, g); X = X.ravel() + rng.uniform(-9, 9, X.size); Y = Y.ravel() + rng.uniform(-9, 9, Y.size)
    out = S.outside_dist(X, Y) > 8
    X, Y = X[out], Y[out]
    d = S.smoothstep(0.35, 0.6, S.fbm(X, Y, 500, 3, 301)) * 0.5
    keep = rng.random(X.size) < d
    X, Y = X[keep], Y[keep]
    Z = S.height(X, Y); nz = S.terrain_normal(X, Y, 6.0)[:, 2]
    ok = (nz > 0.85) & (Z < 320)
    for x, y, z in zip(X[ok], Y[ok], Z[ok]):
        sc = rng.uniform(2.0, 3.4)
        fam = "Y" if rng.random() < 0.3 else "G"
        inst.append(dict(proto=f"SM_PineFar_{fam}", pos=[x, y, z], yaw=float(rng.uniform(0, 360)), scale=[sc, sc, sc],
                         layer="near"))
    return inst


def scatter_rocks():
    inst = []
    centres = 0
    while centres < 55:
        x, y = rng.uniform(30, S.MAP - 30, 2)
        if S.terrain_normal(np.array([x]), np.array([y]))[0, 2] < 0.9:
            continue
        centres += 1
        k = rng.integers(3, 8)
        for j in range(k):
            big = j == 0
            sx = rng.uniform(2.8, 5.5) if big else rng.uniform(0.8, 2.4)
            px = x + (0 if big else rng.normal(0, 5)); py = y + (0 if big else rng.normal(0, 5))
            pz = float(S.height(np.array([px]), np.array([py]))[0])
            scl = [sx * rng.uniform(1.0, 1.5), sx, sx * rng.uniform(0.55, 0.85)]
            c = np.array([px, py, pz])
            if not clear_of_route(c, max(scl), 22.0):
                continue
            inst.append(dict(proto=f"SM_Rock_{rng.integers(4)}", pos=[px, py, pz - 0.15 * scl[2]],
                             yaw=float(rng.uniform(0, 360)), scale=scl, layer="play"))
    return inst


def outcrops():
    """Rock protrusions on the main peak's mid-slope (separate instanced meshes)."""
    inst = []; tries = 0
    angles = [20, 75, 130, 200, 255, 310, 345]
    for a in angles:
        for rad in np.arange(60, 190, 4.0):
            x = S.PEAK_C[0] + rad * np.cos(np.radians(a)); y = S.PEAK_C[1] + rad * np.sin(np.radians(a))
            hp = S.peak_height(np.array([x]), np.array([y]))[0]
            if hp < 150:
                break
        z = float(S.height(np.array([x]), np.array([y]))[0])
        scl = [rng.uniform(16, 26), rng.uniform(9, 14), rng.uniform(12, 20)]
        c = np.array([x, y, z])
        if not clear_of_route(c, max(scl), 24.0):
            continue
        inst.append(dict(proto=f"SM_Rock_{rng.integers(4)}", pos=[x, y, z - 0.25 * scl[2]], yaw=float(a + rng.uniform(-20, 20)),
                         scale=scl, layer="outcrop", pitch=float(rng.uniform(-12, 12))))
    return inst


def start_pad():
    m = Mesh()
    z0 = float(S.height(np.array([S.START_C[0]]), np.array([S.START_C[1]]))[0])
    sides = 24; ang = np.arange(sides) * 2 * np.pi / sides
    R = 15.0; top = z0 + 1.3
    ring = lambda r, z: np.stack([S.START_C[0] + r * np.cos(ang), S.START_C[1] + r * np.sin(ang), np.full(sides, z)], 1)
    lo, hi = ring(R + 0.6, z0 - 1.5), ring(R, top)
    c = np.array([S.START_C[0], S.START_C[1], top])
    gray, gray2, red = PAL_INDEX["pad"][0], PAL_INDEX["pad"][1], PAL_INDEX["pad_mark"][0]
    for i in range(sides):
        j = (i + 1) % sides
        m.quad(lo[i], lo[j], hi[j], hi[i], gray2); m.tri(hi[i], hi[j], c, gray)
    a1, a2 = ring(6.0, top + 0.05), ring(8.0, top + 0.05); d1 = ring(2.2, top + 0.05)
    for i in range(sides):
        j = (i + 1) % sides
        m.quad(a1[i], a1[j], a2[j], a2[i], red); m.tri(d1[i], d1[j], c + [0, 0, 0.05], red)
    return m, top


def path_guide():
    m = Mesh(); p = PAL_INDEX["guide"][0]
    s = np.arange(0, S.PATH_LEN, 5.0); P, T = S.path_frames(s)
    sides = 5; r = 0.35; prev = None
    for k in range(len(s)):
        t = T[k]; y = np.cross([0, 0, 1.0], t); y /= np.linalg.norm(y); z = np.cross(t, y)
        ring = np.array([P[k] + r * (np.cos(a) * y + np.sin(a) * z) for a in np.arange(sides) * 2 * np.pi / sides])
        if prev is not None:
            for i in range(sides):
                j = (i + 1) % sides
                m.quad(prev[i], ring[i], ring[j], prev[j], p)
        prev = ring
    return m


def inst_matrix(it):
    yaw = np.radians(it["yaw"]); pitch = np.radians(it.get("pitch", 0.0))
    Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
    Ry = np.array([[np.cos(pitch), 0, np.sin(pitch)], [0, 1, 0], [-np.sin(pitch), 0, np.cos(pitch)]])
    return Rz @ Ry @ np.diag(it["scale"])


if __name__ == "__main__":
    static = {}
    play = grid_tris(0, S.MAP, 0, S.MAP, S.CELL, 0.3, skirt=60.0)
    static["SM_Terrain_Play"] = (play, color_terrain(play, "play"))
    near = grid_tris(S.NEAR_BOX[0], S.NEAR_BOX[1], S.NEAR_BOX[0], S.NEAR_BOX[1], S.NEAR_CELL, 0.25,
                     hole=(0, S.MAP, 0, S.MAP), skirt=80.0)
    static["SM_Terrain_Near"] = (near, color_terrain(near, "near"))
    far = grid_tris(S.FAR_BOX[0], S.FAR_BOX[1], S.FAR_BOX[0], S.FAR_BOX[1], S.FAR_CELL, 0.2,
                    hole=(S.NEAR_BOX[0], S.NEAR_BOX[1], S.NEAR_BOX[0], S.NEAR_BOX[1]), skirt=200.0)
    static["SM_Terrain_Far"] = (far, color_terrain(far, "far"))
    print({k: len(v[0]) for k, v in static.items()})
    pad, pad_top = start_pad(); static["SM_StartPad"] = pad.arrays()
    static["SM_FlightPath_Guide"] = path_guide().arrays()
    protos = {}
    for kind in "ABC":
        for fam, famname in (("G", "tree_green"), ("Y", "tree_yellow")):
            protos[f"SM_Pine{kind}_{fam}"] = pine_proto(kind, famname).arrays()
    protos["SM_PineFar_G"] = pine_proto("F", "tree_green").arrays()
    protos["SM_PineFar_Y"] = pine_proto("F", "tree_yellow").arrays()
    for i in range(4):
        protos[f"SM_Rock_{i}"] = rock_proto(500 + i).arrays()
    protos["SM_Ring"] = torus(S.RING_RADIUS, S.RING_TUBE, 20, 6, PAL_INDEX["ring"]).arrays()
    protos["_Glider"] = glider().arrays()
    inst = scatter_trees(); print("trees", sum(i["layer"] == "play" for i in inst), "far trees", sum(i["layer"] == "near" for i in inst))
    rk = scatter_rocks(); oc = outcrops(); print("rocks", len(rk), "outcrops", len(oc))
    rings = []
    for k, s in enumerate(S.ring_s_list()):
        p, t = S.path_frames(np.array([s])); p, t = p[0], t[0]
        yaw = np.degrees(np.arctan2(t[1], t[0])); pitch = -np.degrees(np.arcsin(t[2]))
        rings.append(dict(proto="SM_Ring", pos=p.tolist(), yaw=float(yaw), pitch=float(pitch), scale=[1, 1, 1],
                          layer="ring", name=f"Ring_{k:02d}", s=s, section=S.section_name(s)))
    instances = inst + rk + oc + rings
    np.savez_compressed("../build/scene.npz",
                        static_names=np.array(list(static)), proto_names=np.array(list(protos)),
                        **{f"s_v_{k}": v[0] for k, v in static.items()}, **{f"s_p_{k}": v[1] for k, v in static.items()},
                        **{f"p_v_{k}": v[0] for k, v in protos.items()}, **{f"p_p_{k}": v[1] for k, v in protos.items()},
                        palette=np.array(PAL_LIST, np.uint8))
    for it in instances:
        it["pos"] = [float(v) for v in it["pos"]]; it["scale"] = [float(v) for v in it["scale"]]
    json.dump({"instances": instances, "pad_top": pad_top, "palette_index": PAL_INDEX}, open("../build/meta.json", "w"))
    print("instances", len(instances))
