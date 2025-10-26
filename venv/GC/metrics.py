import os, csv, math
import statistics as stats
from typing import List, Dict
import numpy as np

# ---------- helpers ----------
def _percentile(xs: List[float], q: float) -> float:
    if not xs: return 0.0
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = int(k); c = min(f + 1, len(xs) - 1)
    if f == c: return xs[f]
    return xs[f] * (c - k) + xs[c] * (k - f)

def wear_moments(blocks) -> Dict[str, float]:
    """std, cv, gini for erase_count."""
    erases = [b.erase_count for b in blocks]
    if not erases:
        return {"wear_std": 0.0, "wear_cv": 0.0, "wear_gini": 0.0}
    m = sum(erases) / len(erases)
    var = sum((x - m) ** 2 for x in erases) / len(erases)
    std = var ** 0.5
    cv = (std / m) if m > 0 else 0.0
    xs = sorted(erases); n = len(xs); tot = sum(xs)
    if tot == 0:
        g = 0.0
    else:
        cum = 0
        for i, x in enumerate(xs, 1):
            cum += i * x
        g = (2 * cum) / (n * tot) - (n + 1) / n
    return {"wear_std": std, "wear_cv": cv, "wear_gini": g}

def wear_stats(ssd) -> Dict[str, float]:
    """mean, stdev, p50, p95, max (+gini)."""
    ec = [b.erase_count for b in ssd.blocks]
    if not ec:
        return {"wear_mean": 0.0, "wear_stdev": 0.0, "wear_p50": 0.0, "wear_p95": 0.0, "wear_max": 0, "wear_gini": 0.0}
    xs = sorted(ec)
    n = len(xs)
    def pct(p):
        k = (p/100.0)*(n-1)
        f = math.floor(k); c = math.ceil(k)
        if f == c: return float(xs[int(k)])
        return xs[f] + (k-f)*(xs[c]-xs[f])
    gini = wear_moments(ssd.blocks)["wear_gini"]
    return {
        "wear_mean": float(stats.mean(xs)),
        "wear_stdev": float(stats.pstdev(xs)),
        "wear_p50": pct(50),
        "wear_p95": pct(95),
        "wear_max": int(xs[-1]),
        "wear_gini": float(gini),
    }

# ---------- public API ----------
def summarize_metrics(sim) -> None:
    ssd = sim.ssd
    waf = (ssd.device_write_pages / ssd.host_write_pages) if ssd.host_write_pages else 0.0
    avg_erase = sum(b.erase_count for b in ssd.blocks) / ssd.num_blocks
    max_erase = max(b.erase_count for b in ssd.blocks)
    min_erase = min(b.erase_count for b in ssd.blocks)
    wear_delta = max_erase - min_erase

    total_gc_ms = ssd.gc_total_time * 1000.0
    avg_gc_ms = (total_gc_ms / ssd.gc_count) if ssd.gc_count else 0.0
    p50_ms = _percentile(ssd.gc_durations, 0.50) * 1000.0
    p95_ms = _percentile(ssd.gc_durations, 0.95) * 1000.0
    p99_ms = _percentile(ssd.gc_durations, 0.99) * 1000.0

    wm = wear_moments(ssd.blocks)

    print("=== Simulation Result ===")
    print(f"Host writes (pages):   {ssd.host_write_pages:,}")
    print(f"Device writes (pages): {ssd.device_write_pages:,}")
    print(f"WAF (device/host):     {waf:.3f}")
    print(f"GC count:              {ssd.gc_count}")
    print(f"Avg erase per block:   {avg_erase:.2f} (min={min_erase}, max={max_erase}, Δ={wear_delta})")
    print(f"Free pages remaining:  {ssd.free_pages} / {ssd.total_pages}")
    print(f"GC time total / avg:   {total_gc_ms:.2f} ms / {avg_gc_ms:.4f} ms")
    print(f"GC time p50/p95/p99:   {p50_ms:.4f} / {p95_ms:.4f} / {p99_ms:.4f} ms")
    print(f"Wear std/CV/Gini:      {wm['wear_std']:.2f} / {wm['wear_cv']:.4f} / {wm['wear_gini']:.4f}")

SUMMARY_HEADER = [
  "run_id","policy","ops","update_ratio","hot_ratio","hot_weight","seed",
  "trim_enabled","trim_ratio","warmup_fill","bg_gc_every",
  "thr_MBps","iops","lat_p50_ms","lat_p95_ms","lat_p99_ms",
  "host_GB","media_GB","WAF","gc_events","gc_time_ms","wear_std",
  "git_commit","app_version","ts","note"
]

def _num(x):
  try:
    if x is None: return float("nan")
    if isinstance(x, (int, float)): return x
    return float(x)
  except Exception:
    return float("nan")

def append_summary_csv(path, sim, meta: dict):
  """시뮬레이터 결과 + 메타를 표준 스키마로 CSV에 append."""
  row = {
    "run_id": meta.get("run_id") or f"{meta.get('policy','')}_{meta.get('seed','')}",
    "policy": meta.get("policy"),
    "ops": meta.get("ops"),
    "update_ratio": meta.get("update_ratio"),
    "hot_ratio": meta.get("hot_ratio"),
    "hot_weight": meta.get("hot_weight"),
    "seed": meta.get("seed"),
    "trim_enabled": meta.get("trim_enabled", 0),
    "trim_ratio": meta.get("trim_ratio", 0.0),
    "warmup_fill": meta.get("warmup_fill", 0.0),
    "bg_gc_every": meta.get("bg_gc_every", 0),
    # --- 아래 값들은 sim 측에서 수집된 메트릭이 있다고 가정 ---
    "thr_MBps": _num(getattr(getattr(sim, "metrics", sim), "thr_MBps", float("nan"))),
    "iops": _num(getattr(getattr(sim, "metrics", sim), "iops", float("nan"))),
    "lat_p50_ms": _num(getattr(getattr(sim, "metrics", sim), "lat_p50_ms", float("nan"))),
    "lat_p95_ms": _num(getattr(getattr(sim, "metrics", sim), "lat_p95_ms", float("nan"))),
    "lat_p99_ms": _num(getattr(getattr(sim, "metrics", sim), "lat_p99_ms", float("nan"))),
    "host_GB": _num(getattr(getattr(sim, "metrics", sim), "host_GB", float("nan"))),
    "media_GB": _num(getattr(getattr(sim, "metrics", sim), "media_GB", float("nan"))),
    "WAF": _num(getattr(getattr(sim, "metrics", sim), "WAF", float("nan"))),
    "gc_events": _num(getattr(getattr(sim, "metrics", sim), "gc_events", 0)),
    "gc_time_ms": _num(getattr(getattr(sim, "metrics", sim), "gc_time_ms", 0)),
    "wear_std": _num(getattr(getattr(sim, "metrics", sim), "wear_std", float("nan"))),
    "git_commit": meta.get("git_commit", "unknown"),
    "app_version": meta.get("app_version", "v1.0"),
    "ts": meta.get("ts"),
    "note": meta.get("note", ""),
  }

  # 스키마 검증
  for k in SUMMARY_HEADER:
    if k not in row:
      raise ValueError(f"[summary] field missing: {k}")

  os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
  write_header = (not os.path.exists(path)) or os.path.getsize(path) == 0
  with open(path, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=SUMMARY_HEADER)
    if write_header:
      w.writeheader()
    w.writerow(row)

def save_trace_csv(path: str, sim) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cols = ["step","free_pages","device_writes","gc_count","gc_event"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for i in range(len(sim.trace["step"])):
            w.writerow([sim.trace[c][i] for c in cols])

def save_gc_events_csv(path, sim):
  """per-GC 이벤트 CSV 저장. 시뮬레이션 종료 후 호출."""
  events = getattr(sim, "gc_event_log", None) or getattr(getattr(sim, "metrics", sim), "gc_event_log", None)
  if not events:
    # 비어도 파일은 생성(재현성 위해)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
      f.write("step,victim_id,moved_valid,freed_pages,elapsed_ms,cause\n")
    return

  os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
  with open(path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["step","victim_id","moved_valid","freed_pages","elapsed_ms","cause"])
    for e in events:
      w.writerow([
        e.get("step"), e.get("victim_id"), e.get("moved_valid"),
        e.get("freed_pages"), e.get("elapsed_ms"), e.get("cause")
      ])

def summarize_gc_events(gc_events):
    n = len(gc_events)
    if n == 0:
        return {"zgc_ratio": 0.0, "mv_p50": 0, "mv_p95": 0, "mv_p99": 0}
    mv = sorted(ev.get("moved_valid", 0) for ev in gc_events)
    zgc = sum(1 for x in mv if x == 0)
    return {
        "zgc_ratio": zgc / n,
        "mv_p50": float(np.percentile(mv, 50)),
        "mv_p95": float(np.percentile(mv, 95)),
        "mv_p99": float(np.percentile(mv, 99)),
    }