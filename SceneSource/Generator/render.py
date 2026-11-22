"""v2 render driver: instance expansion, variable-speed flight sim, chase camera, stats, stills, video."""
import numpy as np, struct, subprocess, json, sys, os
from PIL import Image, ImageDraw, ImageFont
import scene_common as S
from gen_meshes import inst_matrix

B = "../build"; OUT = "../out"
os.makedirs(OUT, exist_ok=True)
Z = np.load(f"{B}/scene.npz")
PAL = Z["palette"]
META = json.load(open(f"{B}/meta.json"))
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONTB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
ENV = dict(os.environ, SMBOX="-450 -450 1750 1750")
FPS = 30
FOV, FOGK, FOGS = 66.0, 5200.0, 520.0
SEC_CN = {"start_meadow": "草原起点", "canyon": "峡谷", "pass": "山口", "meadow_approach": "草原进场",
          "peak_foot": "山脚 · 开始绕山", "mid_climb": "山腰 · 盘旋爬升", "ridge_crest": "越过山脊", "far_view": "远景展开"}


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz, index=2)


def proto(name):
    return Z[f"p_v_{name}"].astype(np.float64), Z[f"p_p_{name}"]


def expand_instances(layers=None):
    groups = {}
    for it in META["instances"]:
        if layers and it["layer"] not in layers:
            continue
        groups.setdefault(it["proto"], []).append(it)
    Ts, Cs = [], []
    for pn, its in groups.items():
        V, P = proto(pn)
        M = np.array([inst_matrix(it) for it in its]); O = np.array([it["pos"] for it in its])
        T = np.einsum("nij,tkj->ntki", M, V) + O[:, None, None, :]
        Ts.append(T.reshape(-1, 3, 3)); Cs.append(np.tile(PAL[P], (len(its), 1)))
    return np.concatenate(Ts).astype(np.float32), np.concatenate(Cs).astype(np.uint8)


def static_scene(guide=False):
    Ts, Cs = [], []
    for n in Z["static_names"]:
        n = str(n)
        if n == "SM_FlightPath_Guide" and not guide:
            continue
        Ts.append(Z[f"s_v_{n}"]); Cs.append(PAL[Z[f"s_p_{n}"]])
    T, C = expand_instances()
    return np.concatenate(Ts + [T]).astype(np.float32), np.concatenate(Cs + [C]).astype(np.uint8)


def write_mesh(f, tris, cols):
    f.write(struct.pack("i", len(tris)))
    if len(tris):
        f.write(np.ascontiguousarray(tris, np.float32).tobytes()); f.write(np.ascontiguousarray(cols, np.uint8).tobytes())


def write_static(path, guide=False):
    T, C = static_scene(guide)
    with open(path, "wb") as f:
        write_mesh(f, T, C)
    return len(T)

# ---------------------------------------------------------------- flight sim
GL_T, GL_C = proto("_Glider"); GL_C = PAL[GL_C]
DUR = float(S.DURATION)


def emg_demo(t):
    env = np.clip((t - 3.0) / 2.0, 0, 1) * np.clip((DUR - 0.5 - t) / 1.5, 0, 1)
    raw = 0.55 * np.sin(2 * np.pi * t / 7.3) + 0.35 * np.sin(2 * np.pi * t / 3.1 + 1.0)
    return S.EMG_LATERAL_MAX * 0.8 * env * raw


def glider_state(t, offset_fn):
    s = float(S.s_at_time(t)); v = float(S.v_at_s(s))
    p, f = S.path_frames(np.array([s])); p, f = p[0], f[0]
    left = np.cross([0, 0, 1.0], f); left /= np.linalg.norm(left)
    o = offset_fn(t); do = (offset_fn(t + 0.05) - offset_fn(t - 0.05)) / 0.1
    ddo = (offset_fn(t + 0.1) - 2 * o + offset_fn(t - 0.1)) / 0.01
    pos = p - left * o
    fwd = f - left * (do / v); fwd /= np.linalg.norm(fwd)
    bank = float(S.bank_angle(np.array([s]))[0]) + np.arctan(ddo / S.G) * 0.4
    bank = float(np.clip(bank, -np.radians(52), np.radians(52)))
    Y = np.cross([0, 0, 1.0], fwd); Y /= np.linalg.norm(Y); Zv = np.cross(fwd, Y)
    c, sn = np.cos(bank), np.sin(bank)
    R = np.stack([fwd, c * Y + sn * Zv, -sn * Y + c * Zv], 1)
    return dict(t=t, s=s, v=v, pos=pos, fwd=fwd, R=R, bank=bank, offset=o, section=S.section_name(s),
                kappa=float(S.curvature(np.array([s]))[0]))


def simulate(offset_fn=emg_demo, fps=FPS):
    n = int(DUR * fps)
    states = [glider_state(i / fps, offset_fn) for i in range(n)]
    cams = []; cpos = None; roll = 0.0; fsm = None; alpha = 0.0
    a = 1 - np.exp(-1.0 / fps / 0.10)       # position follow (time constant 0.10 s)
    for st in states:
        fsm = st["fwd"] if fsm is None else fsm + (st["fwd"] - fsm) * (1 - np.exp(-1.0 / fps / 0.25))
        fsm = fsm / np.linalg.norm(fsm)
        # orbit the camera around the glider toward the inside of the turn (keeps glider centred,
        # turns the view toward the mountain without letting it fill the frame)
        orbit = st["section"] in ("peak_foot", "mid_climb", "ridge_crest")
        amax = np.radians(36 if orbit else 12)
        ta = np.clip(st["kappa"] * (110 if orbit else 60), -amax, amax)
        alpha += (ta - alpha) * (1 - np.exp(-1.0 / fps / 0.6))
        ca, sa = np.cos(alpha), np.sin(alpha)
        d = np.array([fsm[0] * ca - fsm[1] * sa, fsm[0] * sa + fsm[1] * ca, fsm[2]])
        desired = st["pos"] - d * S.CAM_BACK + np.array([0, 0, S.CAM_UP])
        cpos = desired.copy() if cpos is None else cpos + (desired - cpos) * a
        look = st["pos"] + d * 26 + np.array([0, 0, 1.0])
        f = look - cpos; f /= np.linalg.norm(f)
        roll += (0.35 * st["bank"] - roll) * (1 - np.exp(-1.0 / fps / 0.3))
        Y = np.cross([0, 0, 1.0], f); Y /= np.linalg.norm(Y); Zv = np.cross(f, Y)
        cams.append(dict(pos=cpos.copy(), fwd=f, up=-np.sin(roll) * Y + np.cos(roll) * Zv, alpha=float(alpha)))
    return states, cams


def glider_world(st):
    return np.einsum("ij,tkj->tki", st["R"], GL_T) + st["pos"], GL_C


def trails(hist, cam_pos):
    tris = []
    for side in (1, -1):
        pts = [h["pos"] + h["R"] @ np.array([-0.85, side * S.GLIDER_HALF_SPAN, 0.75]) for h in hist]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]; d = b - a
            if np.linalg.norm(d) < 1e-3 or min(np.linalg.norm(a - cam_pos), np.linalg.norm(b - cam_pos)) < 7.0:
                continue
            v = np.cross(d, cam_pos - a); v /= (np.linalg.norm(v) + 1e-9)
            w = 0.07 * ((i + 1) / len(pts))
            tris += [[a - v * w * 0.8, b - v * w, b + v * w], [a - v * w * 0.8, b + v * w, a + v * w * 0.8]]
    T = np.array(tris, np.float32).reshape(-1, 3, 3)
    return T, np.tile(np.array([[246, 246, 248]], np.uint8), (len(T), 1))


def dyn_for(i, states, cams):
    gT, gC = glider_world(states[i])
    tT, tC = trails(states[max(0, i - 13):i + 1], cams[i]["pos"])
    return np.concatenate([gT, tT]), np.concatenate([gC, tC]), len(gT)


def write_frames(path, items):
    with open(path, "wb") as f:
        f.write(struct.pack("i", len(items)))
        for (cp, fw, up, fov, fogk, fogs, T, C, ngl) in items:
            f.write(struct.pack("13f", *cp, *fw, *up, fov, fogk, fogs, float(ngl)))
            write_mesh(f, T, C)


def run_raster(static_path, frames_path, w, h, ss, stats=None):
    env = dict(ENV)
    if stats:
        env["RSTATS"] = stats
    r = subprocess.run([f"{B}/raster", static_path, frames_path, str(w), str(h), str(ss)], capture_output=True,
                       check=True, env=env)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)


def hud(img, st):
    im = Image.fromarray(img); d = ImageDraw.Draw(im, "RGBA")
    W, H = im.size; k = W / 1280
    d.rounded_rectangle([16 * k, 14 * k, 344 * k, 108 * k], 10 * k, fill=(20, 24, 40, 115))
    d.text((28 * k, 20 * k), f"{SEC_CN[st['section']]}   {st['t']:4.1f}s", font=font(int(19 * k), True), fill=(255, 255, 255, 235))
    d.text((28 * k, 50 * k), f"速度 {st['v']:.0f} m/s   高度 {st['pos'][2]:.0f} m   坡度 {np.degrees(st['bank']):+.0f}°",
           font=font(int(14 * k)), fill=(235, 235, 245, 230))
    d.text((28 * k, 76 * k), "肌电 左/右 (演示输入)", font=font(int(12 * k)), fill=(220, 220, 235, 220))
    bx0, bx1, by = 178 * k, 330 * k, 84 * k
    d.rectangle([bx0, by - 4 * k, bx1, by + 4 * k], fill=(255, 255, 255, 60))
    mid = (bx0 + bx1) / 2; v = st["offset"] / S.EMG_LATERAL_MAX
    d.rectangle([min(mid, mid + v * (bx1 - mid)), by - 4 * k, max(mid, mid + v * (bx1 - mid)), by + 4 * k], fill=(255, 196, 60, 230))
    d.line([mid, by - 7 * k, mid, by + 7 * k], fill=(255, 255, 255, 200), width=max(1, int(k)))
    d.text((W - 330 * k, H - 30 * k), "GliderCanyon v2 · 原创低多边形样板", font=font(int(13 * k)), fill=(255, 255, 255, 170))
    return np.array(im)


def render_range(i0, i1, w=1280, h=720, ss=2, tag="full", states=None, cams=None):
    if states is None:
        states, cams = simulate()
    if not os.path.exists(f"{B}/static.bin"):
        write_static(f"{B}/static.bin")
    seg = f"{B}/seg_{tag}_{i0:05d}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", seg], stdin=subprocess.PIPE)
    for c0 in range(i0, i1, 60):
        items = []
        for i in range(c0, min(i1, c0 + 60)):
            T, C, ng = dyn_for(i, states, cams); cm = cams[i]
            items.append((cm["pos"], cm["fwd"], cm["up"], FOV, FOGK, FOGS, T, C, ng))
        write_frames(f"{B}/frames_{i0}.bin", items)
        frames = run_raster(f"{B}/static.bin", f"{B}/frames_{i0}.bin", w, h, ss, stats=f"{B}/stats_{tag}.txt")
        for j, fr in enumerate(frames):
            ff.stdin.write(hud(fr, states[c0 + j]).tobytes())
    ff.stdin.close(); ff.wait()
    return seg


SHOTS = {"1_canyon_entrance": 3.6, "2_peak_foot_orbit_start": 23.0, "3_mid_climb": 39.5, "4_over_ridge_far_view": 55.0}


def render_stills(w=1920, h=1080, ss=3):
    states, cams = simulate()
    write_static(f"{B}/static.bin")
    items, idx = [], []
    for nm, t in SHOTS.items():
        i = int(t * FPS); T, C, ng = dyn_for(i, states, cams); cm = cams[i]
        items.append((cm["pos"], cm["fwd"], cm["up"], FOV, FOGK, FOGS, T, C, ng)); idx.append((nm, i))
    tgt = np.array([780.0, 640.0, 120.0]); cp = np.array([-420.0, -520.0, 620.0])
    f = tgt - cp; f /= np.linalg.norm(f)
    items.append((cp, f, np.array([0, 0, 1.0]), 55.0, 5200.0, 900.0, np.zeros((0, 3, 3), np.float32), np.zeros((0, 3), np.uint8), 0))
    tgt = np.array([835.0, 650.0, 180.0])
    for nm, cp in (("peak_from_north", np.array([900.0, 1250.0, 170.0])), ("peak_from_east", np.array([1260.0, 700.0, 150.0])),
                   ("peak_from_southwest", np.array([520.0, 250.0, 160.0]))):
        f = tgt - cp; f /= np.linalg.norm(f)
        items.append((cp, f, np.array([0, 0, 1.0]), 60.0, FOGK, FOGS, np.zeros((0, 3, 3), np.float32), np.zeros((0, 3), np.uint8), 0))
    write_frames(f"{B}/frames_stills.bin", items)
    frames = run_raster(f"{B}/static.bin", f"{B}/frames_stills.bin", w, h, ss)
    for (nm, i), fr in zip(idx, frames):
        Image.fromarray(fr).save(f"{OUT}/view_{nm}.png")
        Image.fromarray(hud(fr, states[i])).save(f"{OUT}/view_{nm}_hud.png")
    Image.fromarray(frames[len(idx)]).save(f"{OUT}/overview_oblique_v2.png")
    for k, nm in enumerate(("peak_from_north", "peak_from_east", "peak_from_southwest")):
        Image.fromarray(frames[len(idx) + 1 + k]).save(f"{OUT}/{nm}.png")


def render_top(size=2048, ss=2):
    n = write_static(f"{B}/static_top.bin")
    cp = np.array([S.MAP / 2, S.MAP / 2, 3000.0])
    write_frames(f"{B}/frames_top.bin", [(cp, np.array([0, 0, -1.0]), np.array([0, 1.0, 0]), -S.MAP, 1e9, 0.0,
                                          np.zeros((0, 3, 3), np.float32), np.zeros((0, 3), np.uint8), 0)])
    img = run_raster(f"{B}/static_top.bin", f"{B}/frames_top.bin", size, size, ss)[0]
    Image.fromarray(img).save(f"{OUT}/topview_v2_clean.png")
    im = Image.fromarray(img).convert("RGBA"); ov = Image.new("RGBA", im.size); d = ImageDraw.Draw(ov)
    k = size / S.MAP; P = lambda x, y: (x * k, size - y * k)
    s = np.arange(0, S.PATH_LEN, 4.0); Pp, T = S.path_frames(s)
    Rh = np.cross(T, [0, 0, 1.0]); Rh[:, 2] = 0; Rh /= np.linalg.norm(Rh, axis=1, keepdims=True)
    wd = S.EMG_LATERAL_MAX + S.GLIDER_HALF_SPAN
    d.polygon([P(*q[:2]) for q in (Pp + Rh * wd)] + [P(*q[:2]) for q in (Pp - Rh * wd)][::-1], fill=(255, 255, 255, 50))
    d.line([P(x, y) for x, y in S.PATH_P[::8, :2]], fill=(232, 40, 190, 255), width=int(5 * size / 2048), joint="curve")
    for it in META["instances"]:
        if it["layer"] == "ring":
            cx, cy = P(*it["pos"][:2]); r = 14 * size / 2048
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 200, 40, 255), width=int(5 * size / 2048))
    fs = font(int(22 * size / 2048)); fb = font(int(30 * size / 2048), True)
    for tt in range(0, int(DUR) + 1, 5):
        ss_ = S.s_at_time(tt); p, t = S.path_frames(np.array([ss_])); p = p[0]
        cx, cy = P(*p[:2]); d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 255, 255, 255))
        d.text((cx + 9, cy - 12), f"{tt}s · {p[2]:.0f}m", font=fs, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(30, 30, 50, 255))
    for txt, x, y in [("草原起点", 120, 200), ("峡谷", 70, 420), ("山口", 330, 860), ("主峰 368 m", 880, 690),
                      ("东北肩部山脊", 960, 790), ("方山", 520, 400), ("缺口→远景", 1150, 760), ("缺口→远景", 640, 120),
                      ("缺口→远景", 900, 1230), ("缺口→远景", 1150, 150)]:
        cx, cy = P(x, y); bb = d.textbbox((cx, cy), txt, font=fb)
        d.rounded_rectangle([bb[0] - 8, bb[1] - 5, bb[2] + 8, bb[3] + 5], 8, fill=(20, 24, 40, 165))
        d.text((cx, cy), txt, font=fb, fill=(255, 255, 255, 255))
    x0, y0 = 50, size - 70
    d.rectangle([x0 - 20, y0 - 120, x0 + 760, y0 + 40], fill=(20, 24, 40, 170))
    d.line([x0, y0, x0 + 200 * k, y0], fill=(255, 255, 255, 255), width=6); d.text((x0, y0 - 36), "200 m", font=fs, fill=(255, 255, 255, 255))
    d.line([x0, y0 - 95, x0 + 50, y0 - 95], fill=(232, 40, 190, 255), width=6)
    d.text((x0 + 64, y0 - 110), f"航线 {S.PATH_LEN:.0f} m · {DUR:.1f} s · 46–66 m/s · 航点标注时间/高度", font=fs, fill=(255, 255, 255, 255))
    d.text((x0 + 300, y0 - 36), f"白带：安全通道 ±{wd:.1f} m   ○ 光环（可选）", font=fs, fill=(255, 220, 120, 255))
    Image.alpha_composite(im, ov).convert("RGB").save(f"{OUT}/topview_v2_annotated.png")
    return n


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "top":
        print("static tris", render_top())
    elif cmd == "stills":
        render_stills()
    elif cmd == "range":
        render_range(int(sys.argv[2]), int(sys.argv[3]))
