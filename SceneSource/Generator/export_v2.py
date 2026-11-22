"""Export v2: GLB scene (instanced nodes), per-asset GLB/OBJ, palette, instance CSVs (UE coords), spline data."""
import numpy as np, json, struct, os, csv, shutil
from PIL import Image
import scene_common as S
from gen_meshes import inst_matrix

B = "../build"; D = "../deliver/GliderCanyon_v2"
for sub in ("Meshes_GLB", "Meshes_OBJ", "Textures", "Data"):
    os.makedirs(f"{D}/{sub}", exist_ok=True)
Z = np.load(f"{B}/scene.npz"); PAL = Z["palette"]; META = json.load(open(f"{B}/meta.json"))

SW, NCOL = 32, 8
img = np.zeros((SW * NCOL, SW * NCOL, 3), np.uint8)
for i, c in enumerate(PAL):
    r, q = divmod(i, NCOL); img[r * SW:(r + 1) * SW, q * SW:(q + 1) * SW] = c
Image.fromarray(img).save(f"{D}/Textures/T_LowPolyPalette_v2.png")
PNG = open(f"{D}/Textures/T_LowPolyPalette_v2.png", "rb").read()
C_ZUP2YUP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1.0]])


def uv_of(idx):
    r, q = np.divmod(idx, NCOL); return np.stack([(q + 0.5) / NCOL, (r + 0.5) / NCOL], -1)


def to_gltf(v):
    return np.stack([v[..., 0], v[..., 2], -v[..., 1]], -1)


def flat(tris, pal):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return tris.reshape(-1, 3), np.repeat(n, 3, 0), np.repeat(uv_of(pal), 3, 0)


def write_glb(path, meshes, nodes):
    """meshes: dict key -> (tris, pal, material_index); nodes: list (name, key, 4x4 Z-up matrix or None)."""
    bin_ = bytearray(); bvs = []; accs = []; gm = []; mindex = {}
    def view(data, target=None):
        while len(bin_) % 4: bin_.append(0)
        o = len(bin_); bin_.extend(data); bv = {"buffer": 0, "byteOffset": o, "byteLength": len(data)}
        if target: bv["target"] = target
        bvs.append(bv); return len(bvs) - 1
    def acc(arr, typ, mm=False):
        arr = np.ascontiguousarray(arr, np.float32); a = {"bufferView": view(arr.tobytes(), 34962), "componentType": 5126,
                                                          "count": int(arr.shape[0]), "type": typ}
        if mm: a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
        accs.append(a); return len(accs) - 1
    for key, (T, P, mat) in meshes.items():
        pos, nrm, uv = flat(T.astype(np.float64), P)
        gm.append({"name": key, "primitives": [{"attributes": {"POSITION": acc(to_gltf(pos), "VEC3", True),
                   "NORMAL": acc(to_gltf(nrm), "VEC3"), "TEXCOORD_0": acc(uv, "VEC2")}, "material": mat, "mode": 4}]})
        mindex[key] = len(gm) - 1
    gn = []
    for name, key, M in nodes:
        nd = {"name": name, "mesh": mindex[key]}
        if M is not None:
            nd["matrix"] = (C_ZUP2YUP @ M @ np.linalg.inv(C_ZUP2YUP)).T.reshape(-1).tolist()
        gn.append(nd)
    ib = view(PNG)
    while len(bin_) % 4: bin_.append(0)
    g = {"asset": {"version": "2.0", "generator": "GliderCanyon v2 generator"}, "scene": 0,
         "scenes": [{"name": "GliderCanyon_v2", "nodes": list(range(len(gn)))}], "nodes": gn, "meshes": gm,
         "accessors": accs, "bufferViews": bvs, "buffers": [{"byteLength": len(bin_)}],
         "images": [{"name": "T_LowPolyPalette_v2", "bufferView": ib, "mimeType": "image/png"}],
         "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
         "textures": [{"sampler": 0, "source": 0}],
         "materials": [{"name": "M_LowPolyPalette", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 0.92}},
                       {"name": "M_Ring", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 0.5},
                        "emissiveFactor": [0.9, 0.6, 0.1]}]}
    js = json.dumps(g, separators=(",", ":")).encode(); js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(bin_)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942)); f.write(bytes(bin_))


def write_obj(path, name, T, P, mtl="M_LowPolyPalette"):
    pos, nrm, uv = flat(T.astype(np.float64), P); g = to_gltf(pos); gn = to_gltf(nrm)
    with open(path, "w") as f:
        f.write(f"# GliderCanyon v2 - Y-up metres\nmtllib GliderCanyon_v2.mtl\no {name}\nusemtl {mtl}\n")
        f.write("".join(f"v {a:.3f} {b:.3f} {c:.3f}\n" for a, b, c in g))
        f.write("".join(f"vt {u:.5f} {1 - v:.5f}\n" for u, v in uv))
        f.write("".join(f"vn {a:.4f} {b:.4f} {c:.4f}\n" for a, b, c in gn))
        f.write("".join(f"f {i}/{i}/{i} {i+1}/{i+1}/{i+1} {i+2}/{i+2}/{i+2}\n" for i in range(1, len(pos) + 1, 3)))


open(f"{D}/Meshes_OBJ/GliderCanyon_v2.mtl", "w").write(
    "newmtl M_LowPolyPalette\nKd 1 1 1\nmap_Kd ../Textures/T_LowPolyPalette_v2.png\n\nnewmtl M_Ring\nKd 1 1 1\nKe 0.9 0.6 0.1\nmap_Kd ../Textures/T_LowPolyPalette_v2.png\n")

meshes, nodes = {}, []
for n in Z["static_names"]:
    n = str(n); T, P = Z[f"s_v_{n}"], Z[f"s_p_{n}"]
    meshes[n] = (T, P, 0); nodes.append((n, n, None))
    write_glb(f"{D}/Meshes_GLB/{n}.glb", {n: (T, P, 0)}, [(n, n, None)])
    write_obj(f"{D}/Meshes_OBJ/{n}.obj", n, T, P)
for n in Z["proto_names"]:
    n = str(n); T, P = Z[f"p_v_{n}"], Z[f"p_p_{n}"]
    key = "SM_Glider_Placeholder" if n == "_Glider" else n
    meshes[key] = (T, P, 1 if n == "SM_Ring" else 0)
    write_glb(f"{D}/Meshes_GLB/{key}.glb", {key: meshes[key]}, [(key, key, None)])
    write_obj(f"{D}/Meshes_OBJ/{key}.obj", key, T, P, "M_Ring" if n == "SM_Ring" else "M_LowPolyPalette")
cnt = {}
for it in META["instances"]:
    M = np.eye(4); M[:3, :3] = inst_matrix(it); M[:3, 3] = it["pos"]
    cnt[it["proto"]] = cnt.get(it["proto"], 0) + 1
    nodes.append((it.get("name", f"{it['proto']}_{cnt[it['proto']]:04d}"), it["proto"], M))
G = np.eye(4); G[:3, 3] = S.PATH_P[0]; nodes.append(("SM_Glider_Placeholder", "SM_Glider_Placeholder", G))
write_glb(f"{D}/GliderCanyon_v2_Scene.glb", meshes, nodes)

# ---------------------------------------------------------------- instance tables (UE coordinates)
def ue_pos(p): return [round(p[0] * 100, 1), round(-p[1] * 100, 1), round(p[2] * 100, 1)]


CULL = {"play": (180000, 220000), "near": (650000, 800000), "outcrop": (0, 0), "ring": (0, 0)}   # cm start/end
with open(f"{D}/Data/Instances_UE.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Proto", "Layer", "X_cm", "Y_cm", "Z_cm", "Pitch", "Yaw", "Roll", "SX", "SY", "SZ", "CullStart_cm", "CullEnd_cm", "Name"])
    for it in META["instances"]:
        cs, ce = CULL[it["layer"]]
        if it["proto"].startswith("SM_Rock") and it["layer"] == "play":
            cs, ce = 90000, 120000
        w.writerow([it["proto"], it["layer"], *ue_pos(it["pos"]), round(-it.get("pitch", 0.0), 3), round(-it["yaw"], 3), 0,
                    *[round(v, 4) for v in it["scale"]], cs, ce, it.get("name", "")])

# ---------------------------------------------------------------- spline data
smp = []
for s in np.arange(0, S.PATH_LEN, 1.0):
    p, t = S.path_frames(np.array([s])); p, t = p[0], t[0]
    smp.append([round(float(s), 1), round(float(np.interp(s, S.PATH_S, S.PATH_T)), 4), *ue_pos(p), *np.round(p, 3).tolist(),
                round(float(S.v_at_s(s)), 3), round(float(np.degrees(S.bank_angle(np.array([s]))[0])), 3), S.section_name(s)])
with open(f"{D}/Data/FlightSpline_v2_samples_1m.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["S_m", "Time_s", "UE_X_cm", "UE_Y_cm", "UE_Z_cm", "Blender_x_m", "Blender_y_m", "Blender_z_m", "Speed_mps", "Bank_deg", "Section"])
    w.writerows(smp)
rings = [it for it in META["instances"] if it["layer"] == "ring"]
spec = {
    "version": "v2", "frame_note": "Blender: x east, y north, z up (m). UE via Blender FBX: X=x*100, Y=-y*100, Z=z*100 (cm); UE yaw = -yaw.",
    "length_m": float(S.PATH_LEN), "duration_s": float(S.DURATION),
    "sections": {n: {"t0": round(float(S.PATH_T[S.PATH_SECTION_ID == k][0]), 2), "t1": round(float(S.PATH_T[S.PATH_SECTION_ID == k][-1]), 2),
                     "speed_mps": S.SECTION_SPEED[k]} for k, n in enumerate(S.SECTIONS)},
    "control": {"player_input": "EMG left/right only -> lateral offset relative to the spline",
                "emg_lateral_max_m": S.EMG_LATERAL_MAX, "auto": "forward speed, heading along spline, altitude",
                "bank": "smoothed coordinated-turn bank, |bank| <= 50 deg (+ <= 2 deg x lateral accel term)",
                "rings": "optional; overlap = score, miss = continue"},
    "chase_camera": {"back_m": S.CAM_BACK, "up_m": S.CAM_UP, "fov_deg": 66, "orbit_into_turn_max_deg": {"peak": 36, "other": 12}},
    "rings": [{"name": r["name"], "section": r["section"], "s_m": r["s"], "ue_cm": ue_pos(r["pos"]), "ue_yaw": round(-r["yaw"], 2),
               "ue_pitch": round(-r["pitch"], 2)} for r in rings],
    "peak": {"centre_blender_m": S.PEAK_C.tolist(), "summit_m": 368, "shoulder_centre_blender_m": S.SHOULDER_C.tolist()},
}
json.dump(spec, open(f"{D}/Data/FlightSpline_v2.json", "w"), indent=1, ensure_ascii=False)
for fn in ("test_report_v2.json", "render_stats_v2.json"):
    shutil.copy(f"{B}/{fn}", f"{D}/Data/{fn}")
print("meshes", len(meshes), "nodes", len(nodes), "instances", len(META["instances"]))
