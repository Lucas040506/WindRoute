"""Verify the flight corridor: glider (with EMG lateral offset) and chase camera vs terrain/trees."""
import numpy as np, json
import scene_common as S

meta = json.load(open("../build/meta.json"))
L = S.EMG_LATERAL_MAX; span = S.GLIDER_HALF_SPAN
s = np.arange(0, S.PATH_LEN, 2.0)
P, T = S.path_frames(s)
Rh = np.cross(T, [0, 0, 1.0]); Rh[:, 2] = 0; Rh /= np.linalg.norm(Rh, axis=1, keepdims=True)

res = {}
# 1) vertical clearance under the whole swept wing envelope (+-(L+span))
offs = np.linspace(-(L + span), L + span, 17)
vc = np.full(len(s), np.inf)
for o in offs:
    q = P + o * Rh
    vc = np.minimum(vc, q[:, 2] - S.height(q[:, 0], q[:, 1]))
res["min_vertical_clearance_m"] = float(vc.min())
res["min_vertical_clearance_at_s"] = float(s[vc.argmin()])

# 2) lateral free distance: first offset where terrain reaches (path z - 3 m)
scan = np.arange(0, 120.5, 0.5)
free = np.full((2, len(s)), 120.0)
for side, sg in enumerate((-1, 1)):
    blocked = np.zeros(len(s), bool)
    for o in scan:
        q = P + sg * o * Rh
        hit = (S.height(q[:, 0], q[:, 1]) > P[:, 2] - 3.0) & ~blocked
        free[side, hit] = o; blocked |= hit
lat = free.min(0)
res["min_lateral_free_m"] = float(lat.min())
res["min_lateral_free_at_s"] = float(s[lat.argmin()])
res["required_lateral_m"] = L + span

# 3) chase camera (behind + above) for offsets -L, 0, +L : terrain clearance & line of sight
cam_c, los_c = np.inf, np.inf
_, Tb = S.path_frames(s - S.CAM_BACK)
for o in (-L, 0.0, L):
    g = P + o * Rh
    cam = g - Tb * S.CAM_BACK + np.array([0, 0, S.CAM_UP])
    cam_c = min(cam_c, float((cam[:, 2] - S.height(cam[:, 0], cam[:, 1])).min()))
    for f in np.linspace(0, 1, 12):
        q = cam + (g - cam) * f
        los_c = min(los_c, float((q[:, 2] - S.height(q[:, 0], q[:, 1])).min()))
res["min_camera_terrain_clearance_m"] = cam_c
res["min_camera_line_of_sight_clearance_m"] = los_c

# 4) trees inside the swept corridor
from scipy.spatial import cKDTree
kd = cKDTree(P[:, :2])
bad = 0; worst = np.inf
for (x, y, z, sc, h) in meta["trees"]:
    d, i = kd.query([x, y])
    if d < L + span + 6:
        margin = P[i, 2] - (z + h)
        worst = min(worst, margin)
        if margin < 8:
            bad += 1
res["trees_in_corridor_below_8m_margin"] = bad
res["min_tree_top_margin_inside_corridor_m"] = None if worst == np.inf else float(worst)
res["path_length_m"] = float(S.PATH_LEN)
res["speed_mps"] = float(S.GLIDER_SPEED)
res["duration_s"] = float(S.TARGET_DURATION)
res["emg_lateral_max_m"] = L
print(json.dumps(res, indent=1))
json.dump(res, open("../build/corridor_report.json", "w"), indent=1)
ok = res["min_vertical_clearance_m"] > 8 and res["min_lateral_free_m"] >= L + span + 4 \
    and cam_c > 4 and los_c > 2 and bad == 0
print("PASS" if ok else "FAIL")
