"""Summarize a UE CSV-profiler capture: FPS, frame-time percentiles, thread/GPU times, hitches."""
import csv, sys, statistics as st
rows = list(csv.DictReader(open(sys.argv[1])))
rows = [r for r in rows if r.get("FrameTime") not in (None, "", "FrameTime")]
def col(name):
    out = []
    for r in rows:
        try: out.append(float(r[name]))
        except (KeyError, ValueError, TypeError): pass
    return out
ft = sorted(col("FrameTime"))
if not ft: sys.exit("no FrameTime column")
pct = lambda a, p: a[min(len(a) - 1, int(p / 100 * len(a)))]
print(f"frames {len(ft)}  avg FPS {1000 / st.mean(ft):.1f}  median {pct(ft, 50):.2f} ms  p95 {pct(ft, 95):.2f} ms  p99 {pct(ft, 99):.2f} ms  "
      f"1%-low FPS {1000 / pct(ft, 99):.1f}  hitches>33ms {sum(x > 33.3 for x in ft)}")
for n in ("GameThreadTime", "RenderThreadTime", "GPUTime", "RHIThreadTime"):
    v = col(n)
    if v: print(f"{n:17s} avg {st.mean(v):.2f} ms  p95 {pct(sorted(v), 95):.2f} ms")
