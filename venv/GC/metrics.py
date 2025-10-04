import os
import csv
import math
from typing import List, Tuple
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

def _wear_stats(blocks) -> Tuple[float, float, float]:
    """return (std, cv, gini) for erase_count distribution."""
    erases = [b.erase_count for b in blocks] if blocks else []
    if not erases:
        return 0.0, 0.0, 0.0

    mean_e = sum(erases) / len(erases)
    var_e = sum((x - mean_e) ** 2 for x in erases) / len(erases)
    std_e = var_e ** 0.5
    cv_e = (std_e / mean_e) if mean_e > 0 else 0.0

    xs = sorted(erases)
    n = len(xs)
    tot = sum(xs)
    if tot <= 0:
        gini = 0.0
    else:
        cum = 0
        for i, x in enumerate(xs, 1):
            cum += i * x
        gini = (2 * cum) / (n * tot) - (n + 1) / n

    return std_e, cv_e, gini

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