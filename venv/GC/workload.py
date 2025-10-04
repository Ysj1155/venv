import random

def make_workload(
    n_ops: int,
    update_ratio: float,
    ssd_total_pages: int,
    rng_seed: int = 42,
    hot_ratio: float = 0.2,     # LPN 중 "hot" 비중
    hot_weight: float = 0.7     # 접근의 hot 쏠림 정도
):
    """
    - 신규 vs 업데이트 비율은 update_ratio로 동일.
    - LPN을 hot/cold로 나누고, 업데이트 시 hot 쪽이 더 자주 선택되도록 가중.
    """
    rng = random.Random(rng_seed)
    live_lpns = []
    next_lpn = 0

    ops = []
    hot_cut = max(1, int(ssd_total_pages * hot_ratio))

    for _ in range(n_ops):
        new_write = (len(live_lpns) == 0) or (rng.random() >= update_ratio)
        if new_write:
            lpn = next_lpn
            next_lpn += 1
            live_lpns.append(lpn)
            if next_lpn > ssd_total_pages * 4:
                next_lpn = ssd_total_pages * 4
        else:
            # 업데이트: hot에 가중치
            if live_lpns:
                if rng.random() < hot_weight:
                    # hot 영역에서만 선택
                    hot_pool = [x for x in live_lpns if x < hot_cut]
                    pool = hot_pool if hot_pool else live_lpns
                else:
                    pool = live_lpns
                lpn = rng.choice(pool)
            else:
                lpn = 0
        ops.append(lpn)
    return ops

def make_phased_workload(phases, ssd_total_pages:int, base_seed:int=42):
    """
    phases: 리스트[ {n_ops, update_ratio, hot_ratio, hot_weight, trim_ratio, seed(옵션)} ... ]
    반환: make_workload 형태의 ("write"/"trim", lpn) 리스트를 순서대로 이어붙임
    """
    ops = []
    for i, p in enumerate(phases):
        seed = p.get("seed", base_seed + i)
        chunk = make_workload(
            n_ops=p["n_ops"],
            update_ratio=p.get("update_ratio", 0.8),
            ssd_total_pages=ssd_total_pages,
            rng_seed=seed,
            hot_ratio=p.get("hot_ratio", 0.2),
            hot_weight=p.get("hot_weight", 0.85),
            trim_ratio=p.get("trim_ratio", 0.0),
        )
        ops.extend(chunk)
    return ops