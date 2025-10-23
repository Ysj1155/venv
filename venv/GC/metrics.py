import os
import csv
import math
from typing import List, Tuple, Dict
from math import isfinite

# -----------------------------
# Helpers
# -----------------------------
def _percentile(xs: List[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] * (c - k) + xs[c] * (k - f)

def wear_stats(ssd) -> Dict[str, float]:
    ecs = [b.erase_count for b in ssd.blocks]
    n = len(ecs)
    if n == 0:
        return {"wear_mean":0,"wear_std":0,"wear_p95":0,"wear_max":0,"wear_gini":0}
    mean = sum(ecs)/n
    var = sum((x-mean)**2 for x in ecs)/n
    std = var**0.5
    ecs_sorted = sorted(ecs)
    p95 = ecs_sorted[int(0.95*(n-1))]
    mx  = ecs_sorted[-1]
    # Gini
    cum = 0
    for i,x in enumerate(ecs_sorted, start=1):
        cum += i * x
    gini = (2*cum)/(n*sum(ecs)) - (n+1)/n if sum(ecs)>0 else 0.0
    return {
        "wear_mean": mean, "wear_std": std,
        "wear_p95": float(p95), "wear_max": float(mx),
        "wear_gini": float(gini)
    }

# -----------------------------
# Public API
# -----------------------------
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

    wear_std, wear_cv, wear_gini = _wear_stats(ssd.blocks)

    print("=== Simulation Result ===")
    print(f"Host writes (pages):   {ssd.host_write_pages:,}")
    print(f"Device writes (pages): {ssd.device_write_pages:,}")
    print(f"WAF (device/host):     {waf:.3f}")
    print(f"GC count:              {ssd.gc_count}")
    print(f"Avg erase per block:   {avg_erase:.2f} (min={min_erase}, max={max_erase}, Δ={wear_delta})")
    print(f"Free pages remaining:  {ssd.free_pages} / {ssd.total_pages}")
    print(f"GC time total / avg:   {total_gc_ms:.2f} ms / {avg_gc_ms:.4f} ms")
    print(f"GC time p50/p95/p99:   {p50_ms:.4f} / {p95_ms:.4f} / {p99_ms:.4f} ms")
    print(f"Wear std/CV/Gini:      {wear_std:.2f} / {wear_cv:.4f} / {wear_gini:.4f}")

def append_summary_csv(path: str, sim, meta: dict | None = None) -> None:
    """Append a single-row summary for this run.
    NOTE: To keep compatibility with analyze_results.py, we write the 22-column schema."""
    meta = meta or {}
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

    # Ensure parent dir exists
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    headers = [
        "policy","ops","update_ratio","hot_ratio","hot_weight","seed",
        "host_writes","device_writes","WAF","GC_count",
        "avg_erase","min_erase","max_erase","wear_delta",
        "free_pages","total_pages",
        "gc_time_total_ms","gc_time_avg_ms","gc_time_p50_ms","gc_time_p95_ms","gc_time_p99_ms",
        "wear_std", "wear_cv", "wear_gini",
        "note"
    ]

    def _wear_stats(blocks):
        erases = [b.erase_count for b in blocks]
        if not erases: return 0.0, 0.0, 0.0
        m = sum(erases) / len(erases)
        var = sum((x - m) ** 2 for x in erases) / len(erases)
        std = var ** 0.5
        cv = (std / m) if m > 0 else 0.0
        xs = sorted(erases);
        n = len(xs);
        tot = sum(xs)
        if tot == 0:
            g = 0.0
        else:
            cum = 0
            for i, x in enumerate(xs, 1): cum += i * x
            g = (2 * cum) / (n * tot) - (n + 1) / n
        return std, cv, g

    wear_std, wear_cv, wear_gini = _wear_stats(ssd.blocks)

    row = [
        meta.get("policy"), meta.get("ops"), meta.get("update_ratio"),
        meta.get("hot_ratio"), meta.get("hot_weight"), meta.get("seed"),
        ssd.host_write_pages, ssd.device_write_pages, round(waf, 6), ssd.gc_count,
        round(avg_erase, 6), min_erase, max_erase, wear_delta,
        ssd.free_pages, ssd.total_pages,
        round(total_gc_ms, 6), round(avg_gc_ms, 6), round(p50_ms, 6), round(p95_ms, 6), round(p99_ms, 6),
        round(wear_std, 6), round(wear_cv, 6), round(wear_gini, 6),
        meta.get("note", "")
    ]

    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        if new_file:
            w.writerow(headers)
        w.writerow(row)

def save_trace_csv(path: str, sim) -> None:
    """Save per-step trace that Simulator collected."""
    # Ensure parent dir exists
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    cols = ["step","free_pages","device_writes","gc_count","gc_event"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i in range(len(sim.trace["step"])):
            w.writerow([sim.trace[c][i] for c in cols])

def save_gc_events_csv(path: str, sim) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cols = ["step","cause","victim","moved","valid_before","invalid_before","duration_ms","free_pages_after"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for e in sim.ssd.gc_event_log:
            w.writerow([e.get(c, "") for c in cols])

def summarize_gc_events(gc_events):
    n = len(gc_events)
    if n == 0:
        return {"zgc_ratio": 0.0, "mv_p50": 0, "mv_p95": 0, "mv_p99": 0}
    mv = sorted(ev.get("moved_valid", 0) for ev in gc_events)
    zgc = sum(1 for x in mv if x == 0)
    import numpy as np
    return {
        "zgc_ratio": zgc / n,
        "mv_p50": float(np.percentile(mv, 50)),
        "mv_p95": float(np.percentile(mv, 95)),
        "mv_p99": float(np.percentile(mv, 99)),
    }
