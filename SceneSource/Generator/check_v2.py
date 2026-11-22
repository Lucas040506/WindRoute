"""v2 tests: route smoothness, swept-wing 3D clearance (EMG +-12 m), chase-camera clipping & line of sight."""
import numpy as np, json, sys
import scene_common as S
import render as R
from gen_meshes import inst_matrix

res = {}
# ---------------------------------------------------------------- 1) smoothness
t = np.arange(0, R.DUR, 1 / 30)
s = S.s_at_time(t)
bank = np.degrees(S.bank_angle(s))
res["max_bank_deg"] = float(np.abs(bank).max())
res["max_bank_rate_deg_s"] = float(np.abs(np.gradient(bank, t)).max())
z = np.interp(s, S.PATH_S, S.PATH_P[:, 2])
dz = np.gradient(z, t); v = S.v_at_s(s)
res["max_climb_gradient_pct"] = float(np.abs(np.gradient(z, s + 1e-9 * np.arange(len(s)))).max() * 100)
res["max_vertical_accel_g"] = float(np.abs(np.gradient(dz, t)).max() / 9.81)
res["max_speed_change_mps2"] = float(np.abs(np.gradient(v, t)).max())
res["speed_range_mps"] = [float(v.min()), float(v.max())]

# ---------------------------------------------------------------- obstacle spheres (instances)
obs = []
for it in R.META["instances"]:
    if it["layer"] in ("ring", "near"):
        continue
    sc = np.array(it["scale"])
    if it["proto"].startswith("SM_Pine"):
        h = 7.3 * sc[2]; obs.append((np.array(it["pos"]) + [0, 0, h * 0.55], h * 0.45 + 0.5))
    else:
        obs.append((np.array(it["pos"]), float(sc.max()) * 1.25))
OC = np.array([o[0] for o in obs]); OR = np.array([o[1] for o in obs])
from scipy.spatial import cKDTree
OKD = cKDTree(OC)


def obstacle_clear(q):
    d, i = OKD.query(q, k=8)
    return float((d - OR[i]).min())


GR = np.arange(-24, 24.1, 2.0)
GX, GY = np.meshgrid(GR, GR); GX = GX.ravel(); GY = GY.ravel()


def terrain_clear3d(q):
    """min 3D distance from point q to the terrain surface (heightfield sampled on a 2 m grid, radius 24 m)."""
    hx = q[0] + GX; hy = q[1] + GY; h = S.height(hx, hy)
    d = np.sqrt(GX ** 2 + GY ** 2 + (q[2] - h) ** 2)
    below = q[2] - S.height(np.array([q[0]]), np.array([q[1]]))[0]
    return float(min(d.min(), below)) if below > 0 else float(below)

# ---------------------------------------------------------------- 2) swept wing envelope
ss = np.arange(0, S.PATH_LEN, 3.0)
P, T = S.path_frames(ss)
L = np.cross([0, 0, 1.0], T); L /= np.linalg.norm(L, axis=1, keepdims=True)
bk = S.bank_angle(ss)
wing_min = np.inf; wing_at = None; obs_min = np.inf
per_section = {n: np.inf for n in S.SECTIONS}
for k in range(len(ss)):
    up = np.array([0, 0, 1.0])
    for o in np.linspace(-S.EMG_LATERAL_MAX, S.EMG_LATERAL_MAX, 7):
        c = P[k] - L[k] * o
        for tip in (-1, 1):
            q = c + L[k] * tip * S.GLIDER_HALF_SPAN * np.cos(bk[k]) + up * tip * S.GLIDER_HALF_SPAN * np.sin(bk[k])
            d = terrain_clear3d(q)
            sec = S.section_name(ss[k]); per_section[sec] = min(per_section[sec], d)
            if d < wing_min:
                wing_min, wing_at = d, (float(ss[k]), float(o), sec)
            obs_min = min(obs_min, obstacle_clear(q))
res["wingtip_min_3d_clearance_terrain_m"] = wing_min
res["wingtip_min_clearance_where"] = {"s_m": wing_at[0], "emg_offset_m": wing_at[1], "section": wing_at[2]}
res["wingtip_min_clearance_by_section_m"] = {k: round(v, 1) for k, v in per_section.items()}
res["wingtip_min_clearance_trees_rocks_m"] = obs_min

# ---------------------------------------------------------------- 3) chase camera, real rig, constant offsets
cam = {}
for label, off in (("left_-12m", -S.EMG_LATERAL_MAX), ("centre_0m", 0.0), ("right_+12m", S.EMG_LATERAL_MAX), ("demo_emg", None)):
    fn = R.emg_demo if off is None else (lambda tt, off=off: off)
    states, cams = R.simulate(fn, fps=15)
    cmin, los_min, obsmin, blocked = np.inf, np.inf, np.inf, 0
    for st, cm in zip(states, cams):
        cp = cm["pos"]
        cmin = min(cmin, terrain_clear3d(cp)); obsmin = min(obsmin, obstacle_clear(cp))
        seg = cp[None, :] + (st["pos"] - cp)[None, :] * np.linspace(0.05, 0.9, 14)[:, None]
        hz = seg[:, 2] - S.height(seg[:, 0], seg[:, 1])
        dd, ii = OKD.query(seg); oc = (dd - OR[ii]).min()
        los_min = min(los_min, float(hz.min()))
        if hz.min() < 0 or oc < 0:
            blocked += 1
    cam[label] = {"min_camera_terrain_3d_m": round(cmin, 2), "min_camera_obstacle_m": round(obsmin, 2),
                  "min_line_of_sight_height_m": round(los_min, 2), "blocked_frames": blocked, "frames": len(states)}
res["camera"] = cam
res["route"] = {"length_m": float(S.PATH_LEN), "duration_s": float(S.DURATION),
                "sections_s": {n: [round(float(S.PATH_T[S.PATH_SECTION_ID == k][0]), 2), round(float(S.PATH_T[S.PATH_SECTION_ID == k][-1]), 2)]
                               for k, n in enumerate(S.SECTIONS)}}
ok = (wing_min > 8 and obs_min > 5 and all(c["blocked_frames"] == 0 and c["min_camera_terrain_3d_m"] > 3 for c in cam.values()))
res["PASS"] = bool(ok)
json.dump(res, open("../build/test_report_v2.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, indent=1, ensure_ascii=False))
