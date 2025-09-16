def summarize_metrics(sim):
    ssd = sim.ssd
    waf = ssd.device_write_pages / ssd.host_write_pages if ssd.host_write_pages else 0.0
    avg_erase = sum(b.erase_count for b in ssd.blocks) / ssd.num_blocks
    max_erase = max(b.erase_count for b in ssd.blocks)
    min_erase = min(b.erase_count for b in ssd.blocks)

    # wear-leveling 지표(단순): (max - min)
    wear_delta = max_erase - min_erase

    print("=== Simulation Result ===")
    print(f"Host writes (pages):   {ssd.host_write_pages:,}")
    print(f"Device writes (pages): {ssd.device_write_pages:,}")
    print(f"WAF (device/host):     {waf:.3f}")
    print(f"GC count:              {ssd.gc_count}")
    print(f"Avg erase per block:   {avg_erase:.2f} (min={min_erase}, max={max_erase}, Δ={wear_delta})")
    print(f"Free pages remaining:  {ssd.free_pages} / {ssd.total_pages}")
