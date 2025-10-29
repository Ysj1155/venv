from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import csv
import math
import os

# ------------------------------------------------------------
# 내부 유틸
# ------------------------------------------------------------

def _get(obj: Any, names: List[str], default: Any = None) -> Any:
    """여러 후보 속성명 중 존재하는 첫 값을 반환 (중첩 'a.b' 경로 지원)."""
    for name in names:
        cur = obj
        ok = True
        for part in name.split("."):
            if cur is None or not hasattr(cur, part):
                ok = False
                break
            cur = getattr(cur, part)
        if ok:
            return cur
    return default


def _list_stat(xs: List[float]) -> Dict[str, float]:
    if not xs:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "std": 0.0}
    n = len(xs)
    mn = min(xs)
    mx = max(xs)
    avg = sum(xs) / n
    var = sum((x - avg) ** 2 for x in xs) / n
    return {"min": mn, "max": mx, "avg": avg, "std": math.sqrt(var)}


# ------------------------------------------------------------
# 스냅샷(선택적: autotune 등에 사용 가능)
# ------------------------------------------------------------
@dataclass
class StabilitySnapshot:
    transition_rate: float = 0.0  # hot↔cold 전이율(근사)
    reheat_rate: float = 0.0      # cold→hot 재가열율(근사)


def make_stability_snapshot(sim: Any, hot_thr: float = 0.33, cold_thr: float = 0.05) -> StabilitySnapshot:
    """블록의 inv_ewma 분포로부터 전이/재가열 신호를 근사(단일 스냅샷 기반, 보수적).
    - 실제 전이율은 시계열 필요. 여기서는 분포 퍼짐/꼬리 비중으로 근사 신호만 만든다.
    - CatPolicy.autotune()과 함께 쓸 때 보수적으로 반응하도록 작은 값으로 클램프.
    """
    ssd = getattr(sim, "ssd", sim)
    blocks = getattr(ssd, "blocks", []) or []
    if not blocks:
        return StabilitySnapshot()
    h = sum(1 for b in blocks if float(getattr(b, "inv_ewma", 0.0)) >= hot_thr)
    c = sum(1 for b in blocks if float(getattr(b, "inv_ewma", 0.0)) <= cold_thr)
    n = max(1, len(blocks))
    # 분포가 양극화(핫/콜드 꼬리의 합이 크다) → 전이/재가열 가능성 ↑ 로 해석
    pol = (h + c) / n
    # 보수적 스케일링(너무 크게 튀지 않도록 0.0~0.3 범위)
    return StabilitySnapshot(transition_rate=min(0.3, pol * 0.2), reheat_rate=min(0.3, h / n * 0.1))


# ------------------------------------------------------------
# 메트릭 수집
# ------------------------------------------------------------

def collect_run_metrics(sim: Any) -> Dict[str, Any]:
    """시뮬레이터 구현 차이를 흡수하는 견고한 메트릭 추출기.
    - sim 또는 sim.ssd 아래에 있는 공통 필드들을 탐색해 집계
    - 누락 시 0/None 기본값으로 안전 처리
    """
    ssd = getattr(sim, "ssd", sim)

    host_w = int(_get(ssd, ["host_write_pages", "host_writes", "host_pages"], 0))
    dev_w  = int(_get(ssd, ["device_write_pages", "device_writes", "dev_pages"], 0))
    waf = (dev_w / host_w) if host_w > 0 else 0.0

    gc_cnt = int(_get(ssd, ["gc_count"], 0))
    gc_durs = list(_get(ssd, ["gc_durations"], []) or [])
    gc_avg = (sum(gc_durs) / len(gc_durs)) if gc_durs else 0.0

    free_pages  = int(_get(ssd, ["free_pages"], 0))
    free_blocks = int(_get(ssd, ["free_blocks"], 0))

    blocks = list(getattr(ssd, "blocks", []) or [])
    pages_per_block = int(_get(ssd, ["pages_per_block", "ppb"], 0)) or int(
        _get(sim, ["pages_per_block", "ppb"], 0)
    )

    # wear 통계
    wear_list = [int(getattr(b, "erase_count", 0)) for b in blocks]
    wear_stat = _list_stat([float(x) for x in wear_list])

    # trim, invalid, valid 집계(있으면)
    total_trimmed = sum(int(getattr(b, "trimmed_pages", 0)) for b in blocks)
    total_invalid = sum(int(getattr(b, "invalid_count", 0)) for b in blocks)
    total_valid   = sum(int(getattr(b, "valid_count", 0)) for b in blocks)

    # 정책명 추출(람다면 'lambda'로 표시)
    policy_name = None
    pol = getattr(sim, "gc_policy", None)
    if pol is not None:
        policy_name = getattr(pol, "__name__", str(pol))

    # 장치 크기 추정(가능할 때)
    total_pages = None
    nb = int(_get(ssd, ["num_blocks", "blocks", "total_blocks"], 0))
    if isinstance(getattr(ssd, "num_blocks", None), int):
        nb = getattr(ssd, "num_blocks")
    if nb and pages_per_block:
        total_pages = nb * pages_per_block

    # 스냅샷(선택)
    snap = make_stability_snapshot(sim)

    return {
        "policy": policy_name,
        "host_writes": host_w,
        "device_writes": dev_w,
        "waf": round(waf, 6),
        "gc_count": gc_cnt,
        "gc_avg_s": round(gc_avg, 6),
        "free_pages": free_pages,
        "free_blocks": free_blocks,
        "total_pages": total_pages if total_pages is not None else 0,
        "pages_per_block": pages_per_block,
        "wear_min": wear_stat["min"],
        "wear_max": wear_stat["max"],
        "wear_avg": round(wear_stat["avg"], 6),
        "wear_std": round(wear_stat["std"], 6),
        "trimmed_pages": total_trimmed,
        "valid_pages": total_valid,
        "invalid_pages": total_invalid,
        # autotune용 신호(있으면 사용)
        "transition_rate": round(snap.transition_rate, 6),
        "reheat_rate": round(snap.reheat_rate, 6),
    }


# ------------------------------------------------------------
# 요약 CSV 저장
# ------------------------------------------------------------

def append_summary_csv(path: str, sim: Any, meta: Optional[Dict[str, Any]] = None) -> None:
    """요약 메트릭을 CSV에 append. 파일이 없으면 헤더를 생성.
    - meta 딕셔너리를 받아 컬럼 병합(중복 키는 meta 우선)
    - 정렬된 컬럼 순서로 저장(재현성)
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    metrics = collect_run_metrics(sim)
    row = {**metrics}
    if meta:
        row.update(meta)

    # 기존 파일이 있으면 헤더를 그 파일의 순서로 유지, 없으면 알파벳 정렬
    write_header = not os.path.exists(path)
    if write_header:
        fieldnames = sorted(row.keys())
    else:
        # 기존 헤더를 읽되, 새 컬럼이 생겼다면 뒤에 합쳐서 기록
        with open(path, "r", newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            try:
                header = next(r)
            except StopIteration:
                header = []
        fieldnames = list(header)
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow(row)


# ------------------------------------------------------------
# (선택) 테이블 형태로 요약 행 생성 — 분석 스크립트에서 재사용 가능
# ------------------------------------------------------------

def summary_row(sim: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    row = collect_run_metrics(sim)
    if meta:
        row.update(meta)
    return row