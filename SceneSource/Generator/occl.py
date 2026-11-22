import numpy as np, sys, json, os
import render as R, scene_common as S
label = sys.argv[1]; off = None if label == "demo" else float(sys.argv[2])
fn = R.emg_demo if off is None else (lambda t, o=off: o)
st, cm = R.simulate(fn, fps=30)
idx = list(range(0, len(st), 2))
stats = f"../build/occl_{label}.txt"
if os.path.exists(stats): os.remove(stats)
for c0 in range(0, len(idx), 120):
    items = []
    for i in idx[c0:c0 + 120]:
        T, C, ng = R.dyn_for(i, st, cm); c = cm[i]
        items.append((c["pos"], c["fwd"], c["up"], R.FOV, R.FOGK, R.FOGS, T, C, ng))
    R.write_frames(f"../build/fr_occl_{label}.bin", items)
    R.run_raster("../build/static.bin", f"../build/fr_occl_{label}.bin", 480, 270, 1, stats=stats)
d = np.loadtxt(stats); blk = d[:, 3] / np.maximum(d[:, 1], 1)
print(json.dumps({"label": label, "frames": len(d), "max_glider_fragments_blocked_by_scene": float(blk.max()),
                  "frames_any_block_over_5pct": int((blk > 0.05).sum()),
                  "worst_t_s": float(idx[int(blk.argmax())] / 30)}))
