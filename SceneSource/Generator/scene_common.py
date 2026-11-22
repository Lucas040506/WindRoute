"""GliderCanyon v2 scene definition.

World frame: x = east, y = north, z = up, metres (Blender). UE via Blender FBX: X=x*100, Y=-y*100, Z=z*100 (cm).
Play area: 1300 m square [0,1300]^2. Near ring to [-1750,3000]^2, far ring to [-9000,10250]^2.
"""
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d, maximum_filter1d

MAP = 1300.0
CELL = 8.0
NEAR_BOX = (-1750.0, 3000.0); NEAR_CELL = 25.0
FAR_BOX = (-9000.0, 10250.0); FAR_CELL = 250.0
SEED = 11

# ---------------------------------------------------------------- noise
def _hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def value_noise(x, y, scale, seed=0):
    x = np.asarray(x, float) / scale; y = np.asarray(y, float) / scale
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed); b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed); d = _hash2(ix + 1, iy + 1, seed)
    return (a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy) * 2 - 1


def fbm(x, y, scale, octaves=4, seed=0):
    s, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        s = s + amp * value_noise(x, y, scale / (2 ** o), seed + o * 17)
        tot += amp; amp *= 0.5
    return s / tot


def ridged(x, y, scale, octaves=4, seed=0):
    s, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        n = 1 - np.abs(value_noise(x, y, scale / (2 ** o), seed + o * 23))
        s = s + amp * n * n; tot += amp; amp *= 0.5
    return s / tot


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def seg_dist(px, py, a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ab = b - a; t = np.clip(((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / (ab @ ab), 0, 1)
    return np.hypot(px - (a[0] + t * ab[0]), py - (a[1] + t * ab[1])), t

# ---------------------------------------------------------------- layout
START_C = np.array([180.0, 95.0])
# canyon part of the route (same as v1 for comparison): x, y, z, floor under it
CANYON_CTRL = np.array([
    [175, 40, 10, 0], [182, 150, 24, 0], [195, 245, 30, 0], [222, 340, 31, 0],
    [250, 435, 33, 0], [222, 530, 37, 2], [250, 620, 48, 10], [312, 694, 68, 30],
    [390, 758, 76, 47], [475, 778, 74, 28]], float)
MEADOW_BOX = (430.0, 120.0, 1240.0, 1220.0)
PEAK_C = np.array([835.0, 650.0])        # main horn
SHOULDER_C = np.array([930.0, 735.0])    # north-east shoulder (route crosses it at the end)
FOOT_C = np.array([815.0, 640.0])
# rim gaps / notches: (a, b, half width, floor height)
GAPS = [((1180, 700), (1500, 770), 62, None), ((900, 1170), (960, 1500), 55, None),
        ((1150, 230), (1420, 40), 60, None), ((690, 180), (705, -200), 52, None),
        ((225, 525), (-250, 575), 34, 24.0), ((335, 830), (255, 1500), 48, 58.0)]
SPURS = [((1240, 420), (1110, 450), 45), ((430, 1050), (560, 1080), 40), ((1000, 120), (1010, 230), 42),
         ((1240, 1050), (1150, 1000), 38)]
BUTTES = [(545, 330, 58, 105), (1120, 1100, 50, 120), (1150, 540, 36, 80)]
EMG_LATERAL_MAX = 12.0
GLIDER_HALF_SPAN = 3.2
CAM_BACK, CAM_UP = 11.0, 3.0


def _canyon_poly():
    P = CANYON_CTRL[:, :2]
    out = []
    for i in range(len(P) - 1):
        for t in np.linspace(0, 1, 40, endpoint=False):
            out.append(P[i] + (P[i + 1] - P[i]) * t)
    out.append(P[-1])
    return np.array(out)


_CAN_PTS = None; _CAN_KD = None; _CAN_FLOOR = None


def _canyon_tube():
    global _CAN_PTS, _CAN_KD, _CAN_FLOOR
    if _CAN_KD is None:
        # use the smoothed route samples for the canyon centreline (built below)
        m = PATH_SECTION_ID <= 2          # start, canyon, pass
        _CAN_PTS = PATH_P[m][::2]
        _CAN_FLOOR = PATH_FLOOR[m][::2]
        _CAN_KD = cKDTree(_CAN_PTS[:, :2])
    return _CAN_KD


def sdf_ellipse(x, y, c, r):
    q = np.sqrt(((x - c[0]) / r[0]) ** 2 + ((y - c[1]) / r[1]) ** 2)
    return (q - 1) * min(r)


def sdf_box(x, y, box, rad):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    hx, hy = (box[2] - box[0]) / 2 - rad, (box[3] - box[1]) / 2 - rad
    dx = np.abs(x - cx) - hx; dy = np.abs(y - cy) - hy
    return np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0) - rad


def outside_dist(x, y):
    dx = np.maximum(np.maximum(-x, x - MAP), 0); dy = np.maximum(np.maximum(-y, y - MAP), 0)
    return np.hypot(dx, dy)

# ---------------------------------------------------------------- peak
TERRACES = [(96.0, 22.0, 0.3), (165.0, 20.0, 2.1), (225.0, 14.0, 4.0)]   # level above floor, width, sector phase


def peak_height(x, y):
    """Independent main mountain: foot mound + asymmetric horn + western shoulder, with ledges."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    # foot (gentle, grassy)
    r0 = np.hypot(x - FOOT_C[0], y - FOOT_C[1])
    foot = 48 * np.clip(1 - (r0 / 255) ** 2, 0, 1) ** 2
    # horn: lobed ridges + leaning summit
    dx, dy = x - PEAK_C[0], y - PEAK_C[1]
    th = np.arctan2(dy, dx); r = np.hypot(dx, dy)
    lobes = 1 + 0.20 * np.sin(3 * th + 0.5) + 0.07 * np.sin(7 * th + 1.9) + 0.07 * fbm(x, y, 55, 2, SEED + 31)
    rr = r * lobes
    horn = 300 * np.clip(1 - (rr / 178) ** 1.55, 0, 1) ** 1.15
    # summit spike (leaning north-east) for a distinct silhouette
    sx, sy = x - (PEAK_C[0] - 16), y - (PEAK_C[1] - 12)
    spike = 88 * np.clip(1 - np.hypot(sx, sy) / 62, 0, 1) ** 1.5
    # shoulder
    r2 = np.hypot(x - SHOULDER_C[0], y - SHOULDER_C[1]) * (1 + 0.1 * fbm(x, y, 40, 2, SEED + 41))
    shoulder = 178 * np.clip(1 - r2 / 112, 0, 1) ** 1.35
    h = np.maximum(np.maximum(foot, horn + spike), shoulder)
    # ledges (grass platforms) on some sectors of the mid-slope
    for L, W, ph in TERRACES:
        m = smoothstep(0.15, 0.55, np.sin(2 * th + ph))
        over = np.clip(h - L, 0, W)
        h = h - m * 0.82 * over
    return h


def meadow_floor(x, y):
    return 16 + 11 * fbm(x, y, 210, 3, SEED + 2) + 3.5 * fbm(x, y, 55, 2, SEED + 7)


def far_floor(x, y):
    return 22 + 34 * fbm(x, y, 900, 3, SEED + 61)


def height(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    shp = x.shape; x = x.ravel(); y = y.ravel()
    kd = _canyon_tube()
    dist, idx = kd.query(np.stack([x, y], 1))
    fl_tube = _CAN_FLOOR[idx]
    d_tube = dist - (40 + 6 * fbm(x, y, 90, 3, SEED + 5))
    d_start = sdf_ellipse(x, y, START_C + [0, 20], (135, 125)) + 5 * fbm(x, y, 70, 2, SEED + 9)
    d_mead = sdf_box(x, y, MEADOW_BOX, 170) + 62 * fbm(x, y, 320, 2, SEED + 3) + 22 * fbm(x, y, 95, 2, SEED + 4)
    # spurs: plateau tongues reaching into the meadow
    for (sa, sb, sw) in SPURS:
        dd, _ = seg_dist(x, y, sa, sb)
        d_mead = np.maximum(d_mead, sw - dd)
    d_gap = np.full_like(x, 1e9); fl_gap = np.zeros_like(x)
    for a, b, w, fl in GAPS:
        dd, t = seg_dist(x, y, a, b)
        dd = dd - w * (1 + 0.15 * fbm(x, y, 60, 2, SEED + 13))
        g = fl if fl is not None else 16
        fval = g + (far_floor(x, y) - g) * smoothstep(0.35, 1.0, t)
        sel = dd < d_gap
        d_gap = np.where(sel, dd, d_gap); fl_gap = np.where(sel, fval, fl_gap)
    regions = [(d_tube, fl_tube), (d_start, 0.6 * fbm(x, y, 60, 2, SEED + 1)), (d_mead, meadow_floor(x, y)),
               (d_gap, fl_gap)]
    D = np.stack([r[0] for r in regions]); d = D.min(0)
    w = np.exp(-np.clip(D - d, 0, 80) / 10.0); w /= w.sum(0)
    floor = sum(w[i] * regions[i][1] for i in range(len(regions)))
    # plateau: staggered ridges (ridged noise), designed massifs, falls off outside the play square
    e = outside_dist(x, y)
    plateau = 62 + 120 * ridged(x, y, 300, 4, SEED + 11) ** 1.3 + 16 * fbm(x, y, 120, 3, SEED + 12)
    pc = np.array([390.0, 758.0])
    plateau += 55 * np.exp(-(((x - pc[0]) ** 2 + (y - pc[1]) ** 2) / (150.0 ** 2)))
    plateau += 70 * np.exp(-(((x - 1010) ** 2 + (y - 1300) ** 2) / (170.0 ** 2)))     # north rim crag
    plateau += 60 * np.exp(-(((x - 60) ** 2 + (y - 900) ** 2) / (160.0 ** 2)))       # west crag
    ff = far_floor(x, y)
    plateau = plateau + (ff - plateau) * smoothstep(0, 520, e)
    # cliff profile: two-step ledge, height-dependent jitter
    t = np.clip(d / 28.0, 0, 1)
    prof = 0.5 * smoothstep(0, 0.42, t) + 0.5 * smoothstep(0.55, 1.0, t)
    base = np.where(e > 0, np.minimum(floor, ff), floor)
    h = base + (plateau - base) * prof
    h += 4.5 * fbm(x * 1.7, y * 1.7, 25, 2, SEED + 21) * (prof * (1 - prof) * 4)
    # isolated buttes (mid-ground)
    for (bx, by, br, bh) in BUTTES:
        rb = np.hypot(x - bx, y - by) * (1 + 0.12 * fbm(x, y, 35, 2, SEED + 51))
        top = bh + 6 * fbm(x, y, 40, 2, SEED + 52)
        prof_b = 0.55 * smoothstep(br, br - 14, rb) + 0.45 * smoothstep(br - 20, br - 34, rb)
        h = np.maximum(h, floor + top * prof_b)
    # peak (inside meadow only)
    h += peak_height(x, y)
    # distant ranges
    m = smoothstep(1500, 3600, e) * (0.45 + 0.55 * smoothstep(-0.3, 0.5, fbm(x, y, 3000, 2, SEED + 71)))
    h += m * (180 + 620 * ridged(x, y, 2100, 4, SEED + 73) ** 1.5)
    return h.reshape(shp)


def terrain_normal(x, y, e=2.0):
    hx = (height(x + e, y) - height(x - e, y)) / (2 * e)
    hy = (height(x, y + e) - height(x, y - e)) / (2 * e)
    n = np.stack([-hx, -hy, np.ones_like(hx)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)

# ---------------------------------------------------------------- route
SPIRAL_TH0, SPIRAL_SWEEP = 98.0, -400.0   # clockwise
SPIRAL_Z0, SPIRAL_Z1 = 64.0, 250.0
SECTIONS = ["start_meadow", "canyon", "pass", "meadow_approach", "peak_foot", "mid_climb", "ridge_crest", "far_view"]


def _spiral():
    th = np.radians(np.arange(SPIRAL_TH0, SPIRAL_TH0 + SPIRAL_SWEEP - 0.1, -1.0))
    u = (th - th[0]) / (th[-1] - th[0])
    radii = np.arange(20, 420, 2.0)
    for it in range(3):
        z = SPIRAL_Z0 + (SPIRAL_Z1 - SPIRAL_Z0) * (u - np.sin(2 * np.pi * u) / (2 * np.pi) * 0.1)
        r = _spiral_radius(th, z, radii)
        xy = np.stack([r * np.cos(th), r * np.sin(th)], 1)
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
        u = L / L[-1]
    z = SPIRAL_Z0 + (SPIRAL_Z1 - SPIRAL_Z0) * (u - np.sin(2 * np.pi * u) / (2 * np.pi) * 0.1)
    r = _spiral_radius(th, z, radii)
    pts = np.stack([PEAK_C[0] + r * np.cos(th), PEAK_C[1] + r * np.sin(th), z], 1)
    return pts, th, r


def _spiral_radius(th, z, radii):
    r_req = np.zeros(len(th))
    for i, (a, zz) in enumerate(zip(th, z)):
        px = PEAK_C[0] + radii * np.cos(a); py = PEAK_C[1] + radii * np.sin(a)
        obst = meadow_floor(px, py) + peak_height(px, py)
        hit = np.nonzero(obst > zz - 24)[0]
        r_obs = radii[hit[-1]] if len(hit) else 0.0
        r_req[i] = max(r_obs + 52.0, 95.0)
    r = maximum_filter1d(r_req, 41, mode="nearest")
    r = gaussian_filter1d(r, 14, mode="nearest")
    r = np.maximum(r, r_req)
    return gaussian_filter1d(r, 6, mode="nearest")


def catmull_rom(P, n_per_seg=60):
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        def tj(ti, a, b):
            return ti + max(np.linalg.norm(b - a), 1e-6) ** 0.5
        t0 = 0; t1 = tj(t0, p0, p1); t2 = tj(t1, p1, p2); t3 = tj(t2, p2, p3)
        t = np.linspace(t1, t2, n_per_seg, endpoint=False)[:, None]
        A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
        B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
        out.append((t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2)
    out.append(P[-2][None])
    return np.vstack(out)


def build_route():
    sp, th, r = _spiral()
    sp_ctrl = sp[::15]
    if np.linalg.norm(sp_ctrl[-1] - sp[-1]) > 1:
        sp_ctrl = np.vstack([sp_ctrl, sp[-1]])
    # exit: continue along the spiral tangent, over the shoulder, then descend toward the south gap
    t_end = sp[-1] - sp[-4]; t_end[2] = 0; t_end /= np.linalg.norm(t_end)
    e1 = sp[-1] + np.r_[t_end[:2] * 130, -6]
    goal = np.array([1135.0, 330.0, SPIRAL_Z1 - 55])
    e2 = e1 + (goal - e1) * 0.5 + np.r_[t_end[:2] * 40, 0]; e2[2] = SPIRAL_Z1 - 30
    e3 = goal
    approach = np.array([[585.0, 845.0, 70.0], [700.0, 900.0, 66.0]])
    ctrl = np.vstack([CANYON_CTRL[:, :3], approach, sp_ctrl, e1, e2, e3])
    pts = catmull_rom(ctrl)
    dd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    s = np.arange(0, dd[-1], 0.5)
    P = np.stack([np.interp(s, dd, pts[:, k]) for k in range(3)], 1)
    # smooth altitude profile (sigma 30 m), keeps turns/climbs gentle
    P[:, 2] = gaussian_filter1d(P[:, 2], 120, mode="nearest")
    # section ids by nearest control index
    seg_d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(ctrl, axis=0), axis=1))]
    kd = cKDTree(ctrl); _, ci = kd.query(P)
    nA = len(CANYON_CTRL); nS = len(sp_ctrl)
    sec = np.zeros(len(P), int)
    # assign by arc length positions of control points along the curve
    ctrl_s = np.array([s[np.argmin(np.linalg.norm(P - c, axis=1))] for c in ctrl])
    bounds = [(0, ctrl_s[2]), (ctrl_s[2], ctrl_s[7]), (ctrl_s[7], ctrl_s[nA - 1]), (ctrl_s[nA - 1], ctrl_s[nA + 2]),
              (ctrl_s[nA + 2], ctrl_s[nA + 2 + int(nS * 0.3)]), (ctrl_s[nA + 2 + int(nS * 0.3)], ctrl_s[nA + 2 + int(nS * 0.85)]),
              (ctrl_s[nA + 2 + int(nS * 0.85)], ctrl_s[nA + 2 + nS] + 60), (ctrl_s[nA + 2 + nS] + 60, 1e9)]
    for k, (a, b) in enumerate(bounds):
        sec[(s >= a) & (s < b)] = k
    floor = np.interp(s, ctrl_s[:nA], CANYON_CTRL[:, 3])
    return s, P, sec, floor, ctrl, ctrl_s, (sp, th, r)


PATH_S, PATH_P, PATH_SECTION_ID, PATH_FLOOR, ROUTE_CTRL, ROUTE_CTRL_S, SPIRAL_INFO = build_route()
PATH_LEN = PATH_S[-1]
_TREE2D = cKDTree(PATH_P[:, :2])

# ---------------------------------------------------------------- speed / time
SECTION_SPEED = [62.0, 66.0, 62.0, 56.0, 48.0, 46.0, 50.0, 55.0]


def speed_at(s):
    s = np.asarray(s, float)
    sec = PATH_SECTION_ID[np.clip((s / 0.5).astype(int), 0, len(PATH_S) - 1)]
    v = np.array(SECTION_SPEED)[sec]
    return v


_V_RAW = np.array(SECTION_SPEED)[PATH_SECTION_ID]
PATH_V = gaussian_filter1d(_V_RAW, 300, mode="nearest")     # smooth over ~150 m
PATH_T = np.r_[0, np.cumsum(0.5 / (0.5 * (PATH_V[1:] + PATH_V[:-1])))]
DURATION = PATH_T[-1]


def s_at_time(t):
    return np.interp(t, PATH_T, PATH_S)


def v_at_s(s):
    return np.interp(s, PATH_S, PATH_V)


def path_frames(s):
    s = np.clip(s, 0, PATH_LEN - 1e-3)
    p = np.stack([np.interp(s, PATH_S, PATH_P[:, k]) for k in range(3)], -1)
    ds = 4.0
    pa = np.stack([np.interp(np.clip(s - ds, 0, PATH_LEN), PATH_S, PATH_P[:, k]) for k in range(3)], -1)
    pb = np.stack([np.interp(np.clip(s + ds, 0, PATH_LEN), PATH_S, PATH_P[:, k]) for k in range(3)], -1)
    t = pb - pa; t /= np.linalg.norm(t, axis=-1, keepdims=True)
    return p, t


G = 9.81


def curvature(s, ds=14.0):
    _, t0 = path_frames(s - ds); _, t1 = path_frames(s + ds)
    h0 = np.arctan2(t0[..., 1], t0[..., 0]); h1 = np.arctan2(t1[..., 1], t1[..., 0])
    dh = (h1 - h0 + np.pi) % (2 * np.pi) - np.pi
    return dh / (2 * ds)


BANK_MAX = np.radians(50)
_BANK_RAW = np.clip(-np.arctan(PATH_V ** 2 * curvature(PATH_S) / G), -BANK_MAX, BANK_MAX)
PATH_BANK = gaussian_filter1d(_BANK_RAW, 80, mode="nearest")      # sigma 40 m along the route


def bank_angle(s, speed=None):
    return np.interp(s, PATH_S, PATH_BANK)


def section_name(s):
    return SECTIONS[int(PATH_SECTION_ID[int(np.clip(s / 0.5, 0, len(PATH_S) - 1))])]

# rings at arc-length fractions (optional targets)
def ring_s_list():
    out = []
    for name, frac in [("canyon", 0.25), ("canyon", 0.7), ("pass", 0.5), ("peak_foot", 0.5), ("mid_climb", 0.2),
                       ("mid_climb", 0.5), ("mid_climb", 0.8), ("ridge_crest", 0.5), ("far_view", 0.5)]:
        k = SECTIONS.index(name); ss = PATH_S[PATH_SECTION_ID == k]
        out.append(float(ss[0] + (ss[-1] - ss[0]) * frac))
    return out


RING_RADIUS = 7.0
RING_TUBE = 0.7
