import random

def make_workload(n_ops: int, update_ratio: float, ssd_total_pages: int, rng_seed: int = 42):
    """
    간단 모델:
      - 신규 쓰기(새 LPN) : update_ratio의 보완(=1-update_ratio)
      - 업데이트(기존 LPN 덮어쓰기) : update_ratio
    """
    rng = random.Random(rng_seed)
    live_lpns = []
    next_lpn = 0

    ops = []
    for _ in range(n_ops):
        if (len(live_lpns) > 0) and (rng.random() < update_ratio):
            # 기존 중 하나 업데이트
            lpn = rng.choice(live_lpns)
        else:
            # 신규 LPN
            lpn = next_lpn
            next_lpn += 1
            live_lpns.append(lpn)
            if next_lpn > ssd_total_pages * 4:
                # 논리 공간 무제한으로 두면 mapping 커지므로 안전장치
                next_lpn = ssd_total_pages * 4
        ops.append(lpn)
    return ops
