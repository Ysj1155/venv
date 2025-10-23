from typing import List, Tuple
import random

def make_workload(
    n_ops: int,
    update_ratio: float,
    ssd_total_pages: int,
    rng_seed: int = 42,
    hot_ratio: float = 0.2,
    hot_weight: float = 0.7,
    # 신규 옵션 (기본 False라 기존 호출엔 영향 없음)
    enable_trim: bool = False,
    trim_ratio: float = 0.0,   # enable_trim=True일 때만 사용
) -> List:
    """
    반환:
      - enable_trim=False (기본): [lpn, lpn, ...]  ← 기존과 동일
      - enable_trim=True:      [("write"| "trim", lpn), ...]
    """
    rng = random.Random(rng_seed)
    live_lpns: List[int] = []
    next_lpn = 0
    hot_cut = max(1, int(ssd_total_pages * hot_ratio))

    if not enable_trim:
        ops: List[int] = []
        for _ in range(n_ops):
            new_write = (len(live_lpns) == 0) or (rng.random() >= update_ratio)
            if new_write:
                lpn = next_lpn
                next_lpn += 1
                live_lpns.append(lpn)
            else:
                if live_lpns:
                    if rng.random() < hot_weight:
                        hot_pool = [x for x in live_lpns if x < hot_cut]
                        pool = hot_pool if hot_pool else live_lpns
                    else:
                        pool = live_lpns
                    lpn = rng.choice(pool)
                else:
                    lpn = 0
            ops.append(lpn)
        return ops

    ops2: List[Tuple[str, int]] = []
    for _ in range(n_ops):
        if trim_ratio > 0.0 and live_lpns and (rng.random() < trim_ratio):
            lpn = rng.choice(live_lpns)
            ops2.append(("trim", lpn))
            try:
                live_lpns.remove(lpn)
            except ValueError:
                pass
            continue

        new_write = (len(live_lpns) == 0) or (rng.random() >= update_ratio)
        if new_write:
            lpn = next_lpn
            next_lpn += 1
            live_lpns.append(lpn)
        else:
            if live_lpns:
                if rng.random() < hot_weight:
                    hot_pool = [x for x in live_lpns if x < hot_cut]
                    pool = hot_pool if hot_pool else live_lpns
                else:
                    pool = live_lpns
                lpn = rng.choice(pool)
            else:
                lpn = 0
        ops2.append(("write", lpn))
    return ops2

def make_phased_workload(phases, ssd_total_pages: int, base_seed: int = 42) -> List:
    """
    phases: [{"n_ops":..., "update_ratio":..., "hot_ratio":..., "hot_weight":...,
              "trim_ratio":..., "enable_trim":..., "seed":...}, ...]
    반환:
      - 모든 phase가 enable_trim=False 또는 미지정 → [lpn, ...]
      - 하나라도 enable_trim=True → [("write"/"trim", lpn), ...]
    """
    out = []
    made_tuple = False
    for i, p in enumerate(phases):
        chunk = make_workload(
            n_ops=p["n_ops"],
            update_ratio=p.get("update_ratio", 0.8),
            ssd_total_pages=ssd_total_pages,
            rng_seed=p.get("seed", base_seed + i),
            hot_ratio=p.get("hot_ratio", 0.2),
            hot_weight=p.get("hot_weight", 0.85),
            enable_trim=p.get("enable_trim", False),
            trim_ratio=p.get("trim_ratio", 0.0),
        )
        if chunk and isinstance(chunk[0], tuple):
            made_tuple = True
        out.extend(chunk)

    # 혼합을 피하려고, 한 번이라도 튜플이 나오면 전부 튜플로 맞춘다(정수는 write로 변환)
    if made_tuple:
        norm = []
        for x in out:
            if isinstance(x, tuple):
                norm.append(x)
            else:
                norm.append(("write", x))
        return norm
    return out

def only_writes(seq):
    """[("write"/"trim", lpn), ...] → [lpn, ...] 로 변환 (trim은 버림)"""
    out = []
    for x in seq:
        if isinstance(x, tuple):
            op, lpn = x
            if op == "write":
                out.append(lpn)
        else:
            out.append(x)
    return out

def trim_count(seq) -> int:
    """생성된 시퀀스에서 TRIM 개수 확인."""
    c = 0
    for x in seq:
        if isinstance(x, tuple) and x[0] == "trim":
            c += 1
    return c

def make_rocksdb_like_phases(user_pages: int, base_seed: int = 500) -> list:
    """
    아주 단순화된 LSM 패턴:
      - 초기 bulk-load 비슷한 write
      - update-heavy 구간 반복 (compaction 유사 burst)
    """
    bulk = int(user_pages * 0.8)
    burst = int(user_pages * 0.2)
    phases = [{"n_ops": bulk, "update_ratio": 0.2, "hot_ratio": 0.2, "hot_weight": 0.85, "seed": base_seed}]
    for i in range(3):
        phases.append({"n_ops": burst, "update_ratio": 0.9, "hot_ratio": 0.2, "hot_weight": 0.9, "seed": base_seed + i + 1})
        phases.append({"n_ops": burst, "update_ratio": 0.7, "hot_ratio": 0.2, "hot_weight": 0.85, "seed": base_seed + i + 10})
    return phases
