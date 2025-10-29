from __future__ import annotations
from enum import Enum
from typing import Dict, Tuple, Optional, Callable, List
import random
import time

# -----------------------------
# Basic types
# -----------------------------
class PageState(Enum):
    FREE = 0
    VALID = 1
    INVALID = 2


class Block:
    """Physical erase-block with page states and a few counters.

    - 기존 필드/메서드는 그대로 유지
    - 정책 계산용 헬퍼( invalid_ratio(), wear_norm(), last_activity() )와
      TRIM 추적용 trimmed_pages 를 추가
    """
    def __init__(self, pages_per_block: int):
        self.pages_per_block = pages_per_block
        self.pages: List[PageState] = [PageState.FREE] * pages_per_block
        self.valid_count = 0
        self.invalid_count = 0
        self.erase_count = 0

        # timestamps for age/staleness-style policies
        self.last_invalid_step = 0
        self.last_prog_step = 0

        # lightweight block temperature (invalid-event EWMA)
        self.inv_ewma = 0.0

        # optional stream tag ("user"/"hot"/"cold")
        self.stream_id = "user"
        self.pool = "gen"  # 'hot' | 'cold' | 'gen' (정책에서 cold-bias 등에 활용)

        # --- new: TRIM 추적(정책에서 TRIM-aware age 보너스 계산 시 사용) ---
        self.trimmed_pages = 0

    # -------- properties / helpers --------
    @property
    def free_count(self) -> int:
        return self.pages_per_block - self.valid_count - self.invalid_count

    def invalid_ratio(self) -> float:
        used = self.valid_count + self.invalid_count
        return (self.invalid_count / used) if used > 0 else 0.0

    def wear_norm(self, max_erase_seen: int) -> float:
        return (self.erase_count / max_erase_seen) if max_erase_seen > 0 else 0.0

    def last_activity(self) -> int:
        """최근 활동 시각(프로그래밍/무효화 두 축 중 더 최신)"""
        return max(int(self.last_prog_step), int(self.last_invalid_step))

    # -------- low-level ops --------
    def allocate_free_page(self) -> Optional[int]:
        """Find first FREE page, flip to VALID, return its index (or None)."""
        for idx, st in enumerate(self.pages):
            if st == PageState.FREE:
                self.pages[idx] = PageState.VALID
                self.valid_count += 1
                return idx
        return None

    def invalidate_page(self, page_idx: int, step: int = 0, lam: float = 0.02) -> None:
        """Mark a VALID page INVALID (out-of-place overwrite effect)."""
        if self.pages[page_idx] == PageState.VALID:
            self.pages[page_idx] = PageState.INVALID
            self.valid_count -= 1
            self.invalid_count += 1
            self.last_invalid_step = step
            # invalid 이벤트 기반 온도(핫니스) EWMA 업데이트
            self.inv_ewma = (1.0 - lam) * self.inv_ewma + lam * 1.0

    def erase(self) -> None:
        """Erase whole block (reset to FREE, wear++)."""
        self.pages = [PageState.FREE] * self.pages_per_block
        self.invalid_count = 0
        self.valid_count = 0
        self.erase_count += 1
        # 블록이 새로워졌으므로 상태/나이 관련 값 리셋
        self.last_invalid_step = 0
        self.last_prog_step = 0
        self.inv_ewma = 0.0
        self.trimmed_pages = 0


# -----------------------------
# SSD model
# -----------------------------
class SSD:
    """
    Minimal SSD:
      - write_lpn(lpn): host write (out-of-place)
      - trim_lpn(lpn): logical delete (invalidate)
      - collect_garbage(policy): move VALID pages then erase victim
    Extras:
      - optional 3-stream routing (user/hot/cold) during writes/migration
      - GC destination guarantee logic (no-destination crash prevention)
    """

    # 최소 예약 free 블록 수
    RESERVED_FREE_BLOCKS = 2

    def __init__(self, num_blocks: int, pages_per_block: int, rng_seed: int = 42):
        # geometry & state
        self.num_blocks = num_blocks
        self.pages_per_block = pages_per_block
        self.blocks = [Block(pages_per_block) for _ in range(num_blocks)]
        self.rng = random.Random(rng_seed)

        # clock & temperature
        self._step = 0
        self.ewma_lambda = 0.02

        # metrics
        self.host_write_pages = 0
        self.device_write_pages = 0
        self.gc_count = 0
        self.gc_total_time = 0.0
        self.gc_durations: List[float] = []
        self.gc_event_log: List[Dict] = []

        # mappings
        self.mapping: Dict[int, Tuple[int, int]] = {}            # LPN -> (b, p)
        self.reverse_map: Dict[Tuple[int, int], int] = {}        # (b, p) -> LPN

        # write heads
        self.active_block_idx: Optional[int] = None  # single stream
        self.three_stream = False
        self.stream_active = {"user": None, "hot": None, "cold": None}

        # hotness (for 3-stream)
        self.hotness_mode = "recency"            # or "oracle"
        self.recency_tau = 200                   # recent updates <= tau => hot
        self.oracle_hot_cut: Optional[int] = None
        self.lpn_last_write: Dict[int, int] = {} # LPN -> last host-write step

        # optional score probe for debugging
        self.score_probe: Optional[Callable] = None

    # ---------- derived ----------
    @property
    def total_pages(self) -> int:
        return self.num_blocks * self.pages_per_block

    @property
    def free_pages(self) -> int:
        return sum(b.free_count for b in self.blocks)

    @property
    def free_blocks(self) -> int:
        return sum(1 for b in self.blocks if b.free_count == self.pages_per_block)

    # ---------- low-level ops ----------
    def erase_block(self, block_idx: int) -> None:
        """Block.erase() 래퍼(추가 통계/훅을 넣고 싶으면 여기서)."""
        self.blocks[block_idx].erase()

    # ---------- destination guarantee helpers ----------
    def _free_block_indices(self, exclude_idx: int | None = None) -> list[int]:
        return [i for i, b in enumerate(self.blocks)
                if b.free_count == self.pages_per_block and i != exclude_idx]

    def _find_free_block_index(self, exclude_idx: int | None = None, *, for_host: bool = False) -> int | None:
        """
        free 페이지 있는 블록 하나를 찾는다.
        for_host=True 이면, 예약 블록(마지막 RESERVED_FREE_BLOCKS)은 호스트에게 내주지 않는다.
        """
        # 완전 빈 블록(=스크래치 후보) 우선 고려
        empties = self._free_block_indices(exclude_idx)
        if for_host:
            # 예약선 유지: empties가 예약 개수 이하이면 호스트에게는 불가
            if len(empties) > self.RESERVED_FREE_BLOCKS:
                # 예약선을 제외한 나머지 중 하나
                usable = empties[:-self.RESERVED_FREE_BLOCKS]
                return self.rng.choice(usable) if usable else None
            # 완전 빈 블록이 모두 예약이라면, 부분 free 블록을 찾아본다
            for i, b in enumerate(self.blocks):
                if i == exclude_idx:
                    continue
                if 0 < b.free_count < self.pages_per_block:
                    return i
            return None
        else:
            # GC 목적지: 예약 포함 아무거나 허용
            if empties:
                return self.rng.choice(empties)
            # 완전 빈 블록이 없으면 부분 free 블록 탐색
            for i, b in enumerate(self.blocks):
                if i == exclude_idx:
                    continue
                if b.free_count > 0:
                    return i
            return None

    def _ensure_active_block(self, exclude_idx: int | None = None, *, for_host: bool = False) -> int | None:
        """
        활성(목적지) 블록 보장.
        - for_host=True: 예약선(RESERVED_FREE_BLOCKS)을 넘지 않음
        - for_host=False: GC가 목적지 확보할 때 (예약 포함 허용)
        """
        # 1) 기존 활성 블록 재사용(호스트 전용일 때는 예약선 침범 여부 점검)
        cand = self.active_block_idx
        if cand is not None and cand != exclude_idx and self.blocks[cand].free_count > 0:
            # 호스트용이고, 현재 free가 '예약만 남은 상태'라면 cand 사용 금지
            if for_host:
                empties = self._free_block_indices(exclude_idx)
                if len(empties) <= self.RESERVED_FREE_BLOCKS and self.blocks[cand].free_count == self.pages_per_block:
                    cand = None  # 예약 블록이면 폐기
            if cand is not None:
                return cand

        # 2) free 블록 찾기
        j = self._find_free_block_index(exclude_idx=exclude_idx, for_host=for_host)
        if j is not None:
            self.active_block_idx = j
            return j

        # 3) all-invalid 회수 (호스트용일 땐 회수해도 '예약선'을 넘지 않도록)
        for i, b in enumerate(self.blocks):
            if i == exclude_idx:
                continue
            if b.valid_count == 0 and b.invalid_count > 0:
                self.erase_block(i)
                self.active_block_idx = i
                # erase 후 생긴 새 빈 블록은 예약에 포함됨. 호스트 용이면 여기서도 예약선 체크
                if for_host:
                    empties = self._free_block_indices(exclude_idx)
                    if len(empties) <= self.RESERVED_FREE_BLOCKS:
                        # 방금 만든 블록이 예약으로 들어갔으면 호스트에게는 배정하지 않음
                        continue
                return i

        return None

    def _ensure_destination_block(self, victim_idx: int) -> int | None:
        """
        마이그레이션 목적지 블록 반드시 마련(가능하면).
        GC는 예약 블록 사용 허용(for_host=False).
        """
        j = self._find_free_block_index(exclude_idx=victim_idx, for_host=False)
        if j is not None:
            return j
        # all-invalid 회수
        for i, b in enumerate(self.blocks):
            if i == victim_idx:
                continue
            if b.valid_count == 0 and b.invalid_count > 0:
                self.erase_block(i)
                return i
        # 마지막 시도: 활성 보장(예약 포함)
        return self._ensure_active_block(exclude_idx=victim_idx, for_host=False)

    def _alloc_block_for_migration(self, victim_idx: int, lpn: int) -> int | None:
        """
        마이그레이션 목적지 블록 선택.
        - 단일 스트림: 활성 블록 사용
        - (3-stream을 쓰는 경우) victim stream 보존 or 재분류로 확장 가능
        """
        if self.three_stream:
            victim_stream = getattr(self.blocks[victim_idx], "stream_id", "user")
            stream = victim_stream
            self._ensure_stream_block(stream, exclude_idx=victim_idx)
            dst = self.stream_active[stream]
            if dst is None:
                dst = self._find_free_block_index(exclude_idx=victim_idx)
            return dst
        # single-stream
        return self._ensure_active_block(exclude_idx=victim_idx, for_host=False)

    # ---------- GC ----------
    def collect_garbage(self, policy: callable, cause: str = "manual") -> None:
        """
        - policy(blocks) -> victim_idx
        - victim VALID 페이지 마이그레이션 후 erase
        - 목적지 블록 보장 로직 포함(크래시 방지)
        """
        # 1) victim 선택
        victim_idx = policy(self.blocks)
        if victim_idx is None:
            victim_idx = max(
                range(len(self.blocks)),
                key=lambda i: getattr(self.blocks[i], "invalid_count", 0),
                default=None
            )
            if victim_idx is None:
                raise RuntimeError("No victim block available for GC")
        victim = self.blocks[victim_idx]

        # 2) victim이 all-invalid면 목적지 없이 즉시 erase
        if victim.valid_count == 0 and victim.invalid_count > 0:
            self.erase_block(victim_idx)
            # (선택) 이벤트 기록 가능
            return

        # 3) 목적지 블록 선확보(마이그레이션 도중 막히지 않게)
        _ = self._ensure_destination_block(victim_idx)

        # (옵션) 점수/스냅샷
        probe_detail = None
        if self.score_probe is not None:
            try:
                snap = self.score_probe(self.blocks)
                if isinstance(snap, dict):
                    probe_detail = snap.get(victim_idx)
            except Exception:
                probe_detail = None

        # victim 상태 스냅샷
        v_valid, v_invalid = victim.valid_count, victim.invalid_count
        v_ewma, v_erase = victim.inv_ewma, victim.erase_count

        t0 = time.perf_counter()
        moved_valid = 0

        # 4) VALID 페이지 마이그레이션
        for p_idx, st in enumerate(victim.pages):
            if st != PageState.VALID:
                continue
            lpn = self.reverse_map.get((victim_idx, p_idx))
            if lpn is None:
                continue

            dst_idx = self._alloc_block_for_migration(victim_idx, lpn)
            if dst_idx is None:
                dst_idx = self._ensure_destination_block(victim_idx)
                if dst_idx is None:
                    raise RuntimeError("No destination block for migration")

            dst_p = self.blocks[dst_idx].allocate_free_page()
            if dst_p is None:
                # 활성 블록 교체 후 재시도
                self.active_block_idx = None
                dst_idx = self._ensure_destination_block(victim_idx)
                if dst_idx is None:
                    raise RuntimeError("Allocator inconsistency during GC")
                dst_p = self.blocks[dst_idx].allocate_free_page()
                if dst_p is None:
                    raise RuntimeError("Allocator inconsistency during GC (second)")

            # 새 위치 기록
            self.blocks[dst_idx].last_prog_step = self._step
            victim.invalidate_page(p_idx, step=self._step, lam=self.ewma_lambda)
            self.reverse_map.pop((victim_idx, p_idx), None)
            self.mapping[lpn] = (dst_idx, dst_p)
            self.reverse_map[(dst_idx, dst_p)] = lpn
            self.device_write_pages += 1
            moved_valid += 1

        # 5) victim erase & 통계
        free_before = victim.free_count
        freed_pages = self.pages_per_block - free_before
        victim.erase()
        self.gc_count += 1
        dt = time.perf_counter() - t0
        self.gc_total_time += dt
        self.gc_durations.append(dt)

        # 이벤트 로그
        ev = {
            "step": self._step,
            "cause": cause,
            "victim": victim_idx,
            "moved_valid": moved_valid,
            "freed_pages": freed_pages,
            "gc_s": dt,
            "free_blocks_after": self.free_blocks,
            "v_valid": v_valid,
            "v_invalid": v_invalid,
            "v_inv_ewma": v_ewma,
            "v_erase": v_erase,
            # 선택: 정책 점수 스냅샷
            **({"score_detail": probe_detail} if probe_detail is not None else {}),
        }
        self.gc_event_log.append(ev)

    # ---------- hotness / stream helpers ----------
    def _is_hot_lpn(self, lpn: int) -> bool:
        if self.hotness_mode == "oracle" and self.oracle_hot_cut is not None:
            return lpn < self.oracle_hot_cut
        last = self.lpn_last_write.get(lpn, -10**12)
        return (self._step - last) <= int(self.recency_tau)

    def _find_block_with_free(self, exclude_idx: Optional[int] = None) -> Optional[int]:
        cands = [i for i, b in enumerate(self.blocks) if b.free_count > 0 and i != exclude_idx]
        return self.rng.choice(cands) if cands else None

    def _ensure_stream_block(self, stream: str, exclude_idx: Optional[int] = None) -> None:
        idx = self.stream_active.get(stream)
        if idx is not None and self.blocks[idx].free_count > 0:
            # 호스트가 예약 블록을 쓰지 않도록 체크
            empties = self._free_block_indices(exclude_idx)
            if len(empties) <= self.RESERVED_FREE_BLOCKS and self.blocks[idx].free_count == self.pages_per_block:
                idx = None
            else:
                return
        # 완전 빈 블록 중 '예약 제외'에서 선택
        empties = self._free_block_indices(exclude_idx)
        if len(empties) > self.RESERVED_FREE_BLOCKS:
            usable = empties[:-self.RESERVED_FREE_BLOCKS]
            chosen = self.rng.choice(usable) if usable else None
        else:
            # 부분 free 블록이라도 호스트가 쓸 수 있게 허용
            chosen = None
            for i, b in enumerate(self.blocks):
                if i == exclude_idx:
                    continue
                if 0 < b.free_count < self.pages_per_block:
                    chosen = i
                    break
        self.stream_active[stream] = chosen
        if chosen is not None:
            self.blocks[chosen].stream_id = stream

    # ---------- TRIM ----------
    def trim_lpn(self, lpn: int) -> None:
        self._step += 1
        pos = self.mapping.pop(lpn, None)
        if pos is None:
            return
        b, p = pos
        # TRIM은 기존 VALID를 INVALID로 전환 (쓰기 없이)
        if self.blocks[b].pages[p] == PageState.VALID:
            self.blocks[b].pages[p] = PageState.INVALID
            self.blocks[b].valid_count -= 1
            self.blocks[b].invalid_count += 1
            self.blocks[b].last_invalid_step = self._step
            self.blocks[b].inv_ewma = (1.0 - self.ewma_lambda) * self.blocks[b].inv_ewma + self.ewma_lambda * 1.0
            # --- new: TRIM 카운트 증가 ---
            self.blocks[b].trimmed_pages += 1
        self.reverse_map.pop((b, p), None)

    # ---------- host write ----------
    def write_lpn(self, lpn: int) -> None:
        self._step += 1
        # invalidate previous mapping
        if lpn in self.mapping:
            b, p = self.mapping[lpn]
            self.blocks[b].invalidate_page(p, step=self._step, lam=self.ewma_lambda)
            self.reverse_map.pop((b, p), None)

        # pick target block
        if self.three_stream:
            stream = "hot" if self._is_hot_lpn(lpn) else "user"
            self._ensure_stream_block(stream)
            b_idx = self.stream_active[stream]
        else:
            self._ensure_active_block(for_host=True)
            b_idx = self.active_block_idx

        if b_idx is None:
            # 마지막 방어: 아무 free 블록이나 찾아본다
            b_idx = self._find_free_block_index()
            if b_idx is None:
                raise RuntimeError("No free page before GC")

        p_idx = self.blocks[b_idx].allocate_free_page()
        if p_idx is None:
            # 회전
            if self.three_stream:
                self._ensure_stream_block(stream)
                b_idx = self.stream_active[stream]
            else:
                self._ensure_active_block(for_host=True)
                b_idx = self.active_block_idx
            if b_idx is None:
                b_idx = self._find_free_block_index()
            if b_idx is None:
                raise RuntimeError("No free page after rotate")
            p_idx = self.blocks[b_idx].allocate_free_page()
            if p_idx is None:
                raise RuntimeError("Allocator inconsistency")

        # update maps/metrics
        self.lpn_last_write[lpn] = self._step
        self.mapping[lpn] = (b_idx, p_idx)
        self.reverse_map[(b_idx, p_idx)] = lpn
        self.host_write_pages += 1
        self.device_write_pages += 1
        self.blocks[b_idx].last_prog_step = self._step