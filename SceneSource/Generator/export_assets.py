"""Export GLB (glTF 2.0 binary), OBJ+MTL, palette texture, spline & ring data."""
import numpy as np, json, struct, os, io, csv
from PIL import Image
import scene_common as S
import gen_meshes as GM

B = "../build"; D = "../deliver/GliderCanyon_Sample"
for sub in ("Meshes_GLB", "Meshes_OBJ", "Textures", "Data"):
    os.makedirs(f"{D}/{sub}", exist_ok=True)
Z = np.load(f"{B}/scene.npz")
PAL = Z["palette"]
meta = json.load(open(f"{B}/meta.json"))

# ---------------------------------------------------------------- palette texture (8x8 swatches, 32 px)
SW, NCOL = 32, 8
img = np.zeros((SW * NCOL, SW * NCOL, 3), np.uint8)
for i, c in enumerate(PAL):
    r, q = divmod(i, NCOL)
    img[r * SW:(r + 1) * SW, q * SW:(q + 1) * SW] = c
Image.fromarray(img).save(f"{D}/Textures/T_LowPolyPalette.png")
png_bytes = open(f"{D}/Textures/T_LowPolyPalette.png", "rb").read()


def uv_of(idx):
    r, q = np.divmod(idx, NCOL)
    return np.stack([(q + 0.5) / NCOL, (r + 0.5) / NCOL], -1)   # glTF/top-left origin


def to_gltf(v):  # Z-up (x east, y north) -> glTF Y-up
    return np.stack([v[..., 0], v[..., 2], -v[..., 1]], -1)


def flat(tris, pal):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    pos = tris.reshape(-1, 3)
    nrm = np.repeat(n, 3, 0)
    uv = np.repeat(uv_of(pal), 3, 0)
    col = np.repeat(PAL[pal] / 255.0, 3, 0)
    return pos, nrm, uv, col


def mesh_arrays(name):
    return Z[f"v_{name}"].astype(np.float64), Z[f"p_{name}"]

# objects to export --------------------------------------------------------------
objects = []   # (node name, mesh name, tris(world, Z-up), pal, translation(Z-up) or None)
for n in Z["names"]:
    n = str(n)
    if n.startswith("Ring_") or n.startswith("_"):
        continue
    T, P = mesh_arrays(n)
    objects.append((f"SM_{n}", T, P, np.zeros(3)))
# single ring at origin (for instancing) + ring instances
ring = GM.torus(S.RING_RADIUS, S.RING_TUBE, 20, 6, GM.PAL_INDEX["ring"])
rT, rP = ring.arrays()
gT, gP = mesh_arrays("_Glider_local")

# ---------------------------------------------------------------- GLB writer

def write_glb(path, nodes_meshes):
    """nodes_meshes: list of dict(name, tris, pal, matrix (4x4 Z-up world) or None, mesh_key)."""
    bin_ = bytearray(); bufferViews = []; accessors = []; meshes = []; nodes = []
    mesh_index = {}

    def add_view(data, target=None):
        while len(bin_) % 4:
            bin_.append(0)
        off = len(bin_); bin_.extend(data)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            bv["target"] = target
        bufferViews.append(bv); return len(bufferViews) - 1

    def add_acc(arr, typ, minmax=False):
        arr = np.ascontiguousarray(arr, np.float32)
        bv = add_view(arr.tobytes(), 34962)
        a = {"bufferView": bv, "componentType": 5126, "count": int(arr.shape[0]), "type": typ}
        if minmax:
            a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
        accessors.append(a); return len(accessors) - 1

    for nm in nodes_meshes:
        key = nm["mesh_key"]
        if key not in mesh_index:
            pos, nrm, uv, col = flat(nm["tris"], nm["pal"])
            prim = {"attributes": {"POSITION": add_acc(to_gltf(pos), "VEC3", True),
                                   "NORMAL": add_acc(to_gltf(nrm), "VEC3"),
                                   "TEXCOORD_0": add_acc(uv, "VEC2")},
                    "material": 1 if key == "SM_Ring" else 0, "mode": 4}
            meshes.append({"name": key, "primitives": [prim]})
            mesh_index[key] = len(meshes) - 1
        node = {"name": nm["name"], "mesh": mesh_index[key]}
        if nm.get("matrix") is not None:
            M = nm["matrix"]
            C = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1.0]])   # Zup->Yup
            G = C @ M @ np.linalg.inv(C)
            node["matrix"] = G.T.reshape(-1).tolist()    # column-major
        nodes.append(node)
    img_bv = add_view(png_bytes)
    while len(bin_) % 4:
        bin_.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "GliderCanyon sample generator"},
        "scene": 0, "scenes": [{"name": "GliderCanyon", "nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes, "accessors": accessors, "bufferViews": bufferViews,
        "buffers": [{"byteLength": len(bin_)}],
        "images": [{"name": "T_LowPolyPalette", "bufferView": img_bv, "mimeType": "image/png"}],
        "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
        "textures": [{"sampler": 0, "source": 0}],
        "materials": [
            {"name": "M_LowPolyPalette", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
             "metallicFactor": 0.0, "roughnessFactor": 0.92}},
            {"name": "M_Ring", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
             "metallicFactor": 0.0, "roughnessFactor": 0.5}, "emissiveFactor": [0.9, 0.6, 0.1]}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942)); f.write(bytes(bin_))


def ring_matrix(rg):
    x = np.array(rg["forward"]); y = np.cross([0, 0, 1.0], x); y /= np.linalg.norm(y); z = np.cross(x, y)
    M = np.eye(4); M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, rg["pos"]
    return M


all_nodes = [dict(name=n, tris=T, pal=P, matrix=None, mesh_key=n) for (n, T, P, _) in objects]
all_nodes += [dict(name=rg["name"], tris=rT, pal=rP, matrix=ring_matrix(rg), mesh_key="SM_Ring") for rg in meta["rings"]]
glider_M = np.eye(4); glider_M[:3, 3] = S.PATH_P[0]
all_nodes += [dict(name="SM_Glider_Placeholder", tris=gT, pal=gP, matrix=glider_M, mesh_key="SM_Glider_Placeholder")]
write_glb(f"{D}/GliderCanyon_Scene.glb", all_nodes)
# per-asset GLBs (origin-based for rings/glider)
for nd in all_nodes:
    if nd["name"].startswith("Ring_"):
        continue
    write_glb(f"{D}/Meshes_GLB/{nd['name']}.glb", [dict(nd, matrix=None)])
write_glb(f"{D}/Meshes_GLB/SM_Ring.glb", [dict(name="SM_Ring", tris=rT, pal=rP, matrix=None, mesh_key="SM_Ring")])

# ---------------------------------------------------------------- OBJ (Y-up like glTF; Blender/UE default OBJ import)
def write_obj(path, items):
    with open(path, "w") as f:
        f.write("# GliderCanyon sample - Y-up, metres. mtllib below\nmtllib GliderCanyon.mtl\n")
        vo = 1
        for name, T, P in items:
            pos, nrm, uv, _ = flat(T, P)
            f.write(f"o {name}\nusemtl {'M_Ring' if name == 'SM_Ring' else 'M_LowPolyPalette'}\n")
            g = to_gltf(pos); gn = to_gltf(nrm)
            f.write("".join(f"v {a:.4f} {b:.4f} {c:.4f}\n" for a, b, c in g))
            f.write("".join(f"vt {u:.5f} {1 - v:.5f}\n" for u, v in uv))
            f.write("".join(f"vn {a:.4f} {b:.4f} {c:.4f}\n" for a, b, c in gn))
            for t in range(len(T)):
                i = vo + 3 * t
                f.write(f"f {i}/{i}/{i} {i+1}/{i+1}/{i+1} {i+2}/{i+2}/{i+2}\n")
            vo += 3 * len(T)

mtl = """newmtl M_LowPolyPalette
Kd 1 1 1
Ns 10
map_Kd ../Textures/T_LowPolyPalette.png

newmtl M_Ring
Kd 1 1 1
Ke 0.9 0.6 0.1
map_Kd ../Textures/T_LowPolyPalette.png
"""
open(f"{D}/Meshes_OBJ/GliderCanyon.mtl", "w").write(mtl)
write_obj(f"{D}/Meshes_OBJ/GliderCanyon_StaticWorld.obj", [(n, T, P) for (n, T, P, _) in objects])
write_obj(f"{D}/Meshes_OBJ/SM_Ring.obj", [("SM_Ring", rT, rP)])
write_obj(f"{D}/Meshes_OBJ/SM_Glider_Placeholder.obj", [("SM_Glider_Placeholder", gT, gP)])

# ---------------------------------------------------------------- spline + rings data
def ue(p):   # Blender metres -> UE centimetres (FBX route: Y mirrored)
    return [round(p[0] * 100, 2), round(-p[1] * 100, 2), round(p[2] * 100, 2)]

samples = []
for s in np.arange(0, S.PATH_LEN, 1.0):
    p, t = S.path_frames(np.array([s])); p, t = p[0], t[0]
    b = float(np.degrees(S.bank_angle(np.array([s]), S.GLIDER_SPEED)[0]))
    fidx = float(np.interp(s, S.PATH_S, S.PATH_FIDX))
    sec = S.SECTION_NAMES[int(np.clip(round(fidx), 0, len(S.SECTION_NAMES) - 1))]
    samples.append(dict(s_m=float(s), blender_m=p.round(3).tolist(), ue_cm=ue(p), tangent_blender=t.round(4).tolist(),
                        bank_deg=round(b, 2), section=sec))
spline = {
    "description": "GliderCanyon flight spline. Blender frame: x east, y north, z up (m). UE frame (after FBX import from Blender): X=x*100, Y=-y*100, Z=z*100 (cm).",
    "length_m": float(S.PATH_LEN), "speed_mps": float(S.GLIDER_SPEED), "duration_s": float(S.TARGET_DURATION),
    "emg_lateral_max_m": S.EMG_LATERAL_MAX, "glider_half_span_m": S.GLIDER_HALF_SPAN,
    "chase_camera": {"back_m": S.CAM_BACK, "up_m": S.CAM_UP, "fov_deg": 66},
    "control_points": [dict(i=i, blender_m=c.tolist(), ue_cm=ue(c), section=S.SECTION_NAMES[i]) for i, c in enumerate(S.CTRL)],
    "control_point_interpolation": "centripetal Catmull-Rom (UE SplineComponent curve points give a very close match; use the 1 m samples for exactness)",
    "rings": [dict(name=r["name"], s_m=r["s"], blender_m=list(np.round(r["pos"], 3)), ue_cm=ue(r["pos"]),
                   forward_blender=list(np.round(r["forward"], 4)),
                   ue_yaw_deg=round(float(np.degrees(np.arctan2(-r["forward"][1], r["forward"][0]))), 2),
                   ue_pitch_deg=round(float(np.degrees(np.arcsin(r["forward"][2]))), 2),
                   radius_m=S.RING_RADIUS) for r in meta["rings"]],
    "start_pad_center_blender_m": [float(S.START_C[0]), float(S.START_C[1]), meta["pad_top"]],
}
json.dump(spline, open(f"{D}/Data/FlightSpline.json", "w"), indent=1, ensure_ascii=False)
with open(f"{D}/Data/FlightSpline_samples_1m.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Name", "S_m", "UE_X_cm", "UE_Y_cm", "UE_Z_cm", "Blender_x_m", "Blender_y_m", "Blender_z_m", "Bank_deg", "Section"])
    for k, smp in enumerate(samples):
        w.writerow([f"P{k:05d}", smp["s_m"], *smp["ue_cm"], *smp["blender_m"], smp["bank_deg"], smp["section"]])
json.dump(json.load(open(f"{B}/corridor_report.json")), open(f"{D}/Data/corridor_report.json", "w"), indent=1)
print("exported", len(all_nodes), "nodes;", len(samples), "spline samples")
