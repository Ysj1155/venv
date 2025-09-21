import csv, os

def _percentile(xs, q):
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = (len(xs)-1) * q
    f = int(k)
    c = min(f+1, len(xs)-1)
    if f == c:
        return xs[f]
    return xs[f] * (c - k) + xs[c] * (k - f)

def summarize_metrics(sim):
    ssd = sim.ssd
    waf = ssd.device_write_pages / ssd.host_write_pages if ssd.host_write_pages else 0.0
    avg_erase = sum(b.erase_count for b in ssd.blocks) / ssd.num_blocks
    max_erase = max(b.erase_count for b in ssd.blocks)
    min_erase = min(b.erase_count for b in ssd.blocks)
    wear_delta = max_erase - min_erase
    total_gc_ms = ssd.gc_total_time * 1000.0
    avg_gc_ms = (total_gc_ms / ssd.gc_count) if ssd.gc_count else 0.0
    p50_ms = _percentile(ssd.gc_durations, 0.50) * 1000.0
    p95_ms = _percentile(ssd.gc_durations, 0.95) * 1000.0
    p99_ms = _percentile(ssd.gc_durations, 0.99) * 1000.0

    print("=== Simulation Result ===")
    print(f"Host writes (pages):   {ssd.host_write_pages:,}")
    print(f"Device writes (pages): {ssd.device_write_pages:,}")
    print(f"WAF (device/host):     {waf:.3f}")
    print(f"GC count:              {ssd.gc_count}")
    print(f"Avg erase per block:   {avg_erase:.2f} (min={min_erase}, max={max_erase}, Δ={wear_delta})")
    print(f"Free pages remaining:  {ssd.free_pages} / {ssd.total_pages}")
    print(f"GC time total / avg:   {total_gc_ms:.2f} ms / {avg_gc_ms:.4f} ms")
    print(f"GC time p50/p95/p99:   {p50_ms:.4f} / {p95_ms:.4f} / {p99_ms:.4f} ms")

def append_summary_csv(path, sim, meta: dict = None):
    meta = meta or {}
    ssd = sim.ssd
    waf = ssd.device_write_pages / ssd.host_write_pages if ssd.host_write_pages else 0.0
    avg_erase = sum(b.erase_count for b in ssd.blocks) / ssd.num_blocks
    max_erase = max(b.erase_count for b in ssd.blocks)
    min_erase = min(b.erase_count for b in ssd.blocks)
    wear_delta = max_erase - min_erase

    total_gc_ms = ssd.gc_total_time * 1000.0
    avg_gc_ms = (total_gc_ms / ssd.gc_count) if ssd.gc_count else 0.0
    from math import isfinite
    def safe(v): return float(v) if isfinite(v) else 0.0

    from_millis = lambda q: _percentile(ssd.gc_durations, q) * 1000.0
    p50_ms = from_millis(0.50);
    p95_ms = from_millis(0.95);
    p99_ms = from_millis(0.99)

    headers = [
        "policy", "ops", "update_ratio", "hot_ratio", "hot_weight", "seed",
        "host_writes", "device_writes", "WAF", "GC_count",
        "avg_erase", "min_erase", "max_erase", "wear_delta",
        "free_pages", "total_pages",
        "gc_time_total_ms", "gc_time_avg_ms", "gc_time_p50_ms", "gc_time_p95_ms", "gc_time_p99_ms",
        "note"
    ]
    row = [
        meta.get("policy"), meta.get("ops"), meta.get("update_ratio"),
        meta.get("hot_ratio"), meta.get("hot_weight"), meta.get("seed"),
        ssd.host_write_pages, ssd.device_write_pages, round(waf, 6), ssd.gc_count,
        round(avg_erase, 6), min_erase, max_erase, wear_delta,
        ssd.free_pages, ssd.total_pages,
        round(total_gc_ms, 6), round(avg_gc_ms, 6), round(p50_ms, 6), round(p95_ms, 6), round(p99_ms, 6),
        meta.get("note", "")
    ]
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file: w.writerow(headers)
        w.writerow(row)