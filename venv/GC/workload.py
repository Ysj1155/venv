from typing import List, Tuple, Optional
import random

# ------------------------------------------------------------
# 내부 유틸: 인덱스드 리스트 (O(1) add/remove/choice)
# ------------------------------------------------------------
class _IndexList:
    def __init__(self):
        self._arr: List[int] = []
        self._pos: dict[int, int] = {}
    def __len__(self) -> int:
        return len(self._arr)
    def add(self, x: int) -> None:
        if x in self._pos:  # 중복 방지
            return
        self._pos[x] = len(self._arr)
        self._arr.append(x)
    def remove(self, x: int) -> None:
        i = self._pos.pop(x, None)
        if i is None:
            return
        last = self._arr.pop()
        if i < len(self._arr):
            self._arr[i] = last
            self._pos[last] = i
    def choice(self, rng: random.Random) -> int:
        if not self._arr:
            raise IndexError("empty _IndexList")
        return self._arr[rng.randrange(len(self._arr))]
    def to_list(self) -> List[int]:
        return list(self._arr)


# ------------------------------------------------------------
# 메인 워크로드 (인터페이스 동일)
# ------------------------------------------------------------
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

    변경 사항(안전성/성능):
      - next_lpn 이 ssd_total_pages 를 넘지 않도록 안전 가드(넘으면 update로 전환)
      - hot/cold 선택을 리스트 선형검색 대신 O(1) 자료구조로 최적화
    """
    rng = random.Random(rng_seed)

    # hotset 경계 (oracle 스타일: lpn < hot_cut → hot)
    hot_cut = max(1, int(ssd_total_pages * max(0.0, min(hot_ratio, 1.0))))

    # 라이브 LPN 컨테이너(빠른 샘플링/삭제용)
    live_hot = _IndexList()
    live_cold = _IndexList()

    def _is_hot(lpn: int) -> bool:
        return lpn < hot_cut

    def _add_live(lpn: int) -> None:
        (live_hot if _is_hot(lpn) else live_cold).add(lpn)

    def _remove_live(lpn: int) -> None:
        (live_hot if _is_hot(lpn) else live_cold).remove(lpn)

    def _have_live() -> bool:
        return (len(live_hot) + len(live_cold)) > 0

    def _pick_update_lpn() -> int:
        # hot_weight 확률로 hot pool 우선, 비어있으면 다른 풀에서
        if rng.random() < max(0.0, min(hot_weight, 1.0)):
            if len(live_hot) > 0:
                return live_hot.choice(rng)
            if len(live_cold) > 0:
                return live_cold.choice(rng)
        else:
            if len(live_cold) > 0:
                return live_cold.choice(rng)
            if len(live_hot) > 0:
                return live_hot.choice(rng)
        return 0  # 완전 비어있을 때의 안전 기본값

    next_lpn = 0

    # ---- enable_trim = False (기존 반환 형식) ----
    if not enable_trim:
        ops: List[int] = []
        for _ in range(n_ops):
            # 새 write 여부
            new_write = (len(live_hot) + len(live_cold) == 0) or (rng.random() >= update_ratio)
            if new_write and next_lpn < ssd_total_pages:
                lpn = next_lpn
                next_lpn += 1
                _add_live(lpn)
            else:
                # 용량을 다 채웠거나 update 선택 → live 풀에서 선택
                if _have_live():
                    lpn = _pick_update_lpn()
                else:
                    # 빈 시스템에서 update가 걸리는 경우를 방지하기 위한 fallback
                    lpn = min(next_lpn, ssd_total_pages - 1) if ssd_total_pages > 0 else 0
                    if next_lpn < ssd_total_pages:
                        next_lpn += 1
                        _add_live(lpn)
            ops.append(lpn)
        return ops

    # ---- enable_trim = True (튜플 반환) ----
    ops2: List[Tuple[str, int]] = []
    trim_ratio = max(0.0, min(trim_ratio, 1.0))
    for _ in range(n_ops):
        # 1) TRIM 이벤트
        if trim_ratio > 0.0 and _have_live() and (rng.random() < trim_ratio):
            # pool 비율을 반영한 trim (hot_weight로 균형)
            if rng.random() < max(0.0, min(hot_weight, 1.0)) and len(live_hot) > 0:
                lpn = live_hot.choice(rng)
            elif len(live_cold) > 0:
                lpn = live_cold.choice(rng)
            elif len(live_hot) > 0:
                lpn = live_hot.choice(rng)
            else:
                lpn = 0
            ops2.append(("trim", lpn))
            _remove_live(lpn)
            continue

        # 2) WRITE 이벤트 (신규/업데이트)
        new_write = (len(live_hot) + len(live_cold) == 0) or (rng.random() >= update_ratio)
        if new_write and next_lpn < ssd_total_pages:
            lpn = next_lpn
            next_lpn += 1
            _add_live(lpn)
        else:
            if _have_live():
                lpn = _pick_update_lpn()
            else:
                lpn = min(next_lpn, ssd_total_pages - 1) if ssd_total_pages > 0 else 0
                if next_lpn < ssd_total_pages:
                    next_lpn += 1
                    _add_live(lpn)
        ops2.append(("write", lpn))
    return ops2


# ------------------------------------------------------------
# 멀티 페이즈 (그대로 유지, 내부적으로 make_workload 호출)
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# 보조 유틸 (그대로 유지)
# ------------------------------------------------------------
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