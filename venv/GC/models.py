from enum import Enum
from typing import Dict, Tuple, Optional, Callable, List
import random
import time

class PageState(Enum):
    FREE = 0
    VALID = 1
    INVALID = 2

class Block:
    """Physical erase-block with page states and a few counters."""
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
        self.stream_id = "user"  # 기본 스트림 태그

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
            self.inv_ewma = (1.0 - lam) * self.inv_ewma + lam * 1.0

    def erase(self) -> None:
        """Erase whole block (reset to FREE, wear++)."""
        self.pages = [PageState.FREE] * self.pages_per_block
        self.invalid_count = 0
        self.valid_count = 0
        self.erase_count += 1

    @property
    def free_count(self) -> int:
        return self.pages_per_block - self.valid_count - self.invalid_count


class SSD:
    """
    Minimal SSD:
      - write_lpn(lpn): host write (out-of-place)
      - trim_lpn(lpn): logical delete
      - collect_garbage(policy): move VALID pages then erase victim
    Extras:
      - optional 3-stream routing (user/hot/cold) during writes/migration
      - hysteresis GC trigger by free-block ratio
    """
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

        # single-stream write head
        self.active_block_idx: Optional[int] = None

        # 3-stream controls
        self.three_stream = False
        self.stream_active = {"user": None, "hot": None, "cold": None}
        self.hotness_mode = "recency"            # or "oracle"
        self.recency_tau = 200                   # recent updates <= tau => hot
        self.oracle_hot_cut: Optional[int] = None
        self.lpn_last_write: Dict[int, int] = {} # LPN -> last host-write step

        # GC hysteresis thresholds (by free-block ratio)
        self.pool_low_ratio = 0.02
        self.pool_high_ratio = 0.05
        self._gc_force_on = False
        self.score_probe = None

    def collect_garbage(self, policy: callable, cause: str = "manual") -> None:
        """
        - policy(blocks) -> victim_idx 를 준다고 가정.
        - victim의 VALID 페이지를 새 블록으로 마이그레이션 후 erase.
        - 3-stream 모드면 victim의 stream을 보존(또는 _is_hot_lpn 기반 재분류로 변경 가능).
        - 이벤트/시간/카운터를 갱신.
        """
        probe_snapshot = None
        if self.score_probe is not None:
            try:
                probe_snapshot = self.score_probe(self.blocks)  # {idx: {...}}
            except Exception:
                probe_snapshot = None

        # victim_idx = policy(self.blocks) 다음, 이벤트 로그 할 때:
        event = {
            "step": self._step, "cause": cause, "victim": victim_idx,
            "moved_valid": moved_valid, "freed_pages": freed_before,
            "gc_s": dt, "free_blocks_after": self.free_blocks,
        }
        if probe_snapshot is not None and victim_idx in probe_snapshot:
            event["score_detail"] = probe_snapshot[victim_idx]
        self.gc_event_log.append(event)

        # victim 선택
        victim_idx = policy(self.blocks)
        if victim_idx is None:
            return
        victim = self.blocks[victim_idx]

        t0 = time.perf_counter()
        moved_valid = 0

        valid_before = victim.valid_count
        invalid_before = victim.invalid_count

        # VALID 페이지 마이그레이션
        for p_idx, st in enumerate(victim.pages):
            if st != PageState.VALID:
                continue
            lpn = self.reverse_map.get((victim_idx, p_idx))
            if lpn is None:
                continue

            # ✅ 4-B 핵심: 목적지 블록 선택 (stream-aware)
            dst_idx = self._alloc_block_for_migration(victim_idx, lpn)
            if dst_idx is None:
                raise RuntimeError("No destination block for migration")

            dst_p = self.blocks[dst_idx].allocate_free_page()
            if dst_p is None:
                # 한 번 회전해서 재시도
                if self.three_stream:
                    stream = getattr(self.blocks[dst_idx], "stream_id", "user")
                    self._ensure_stream_block(stream, exclude_idx=victim_idx)
                    dst_idx = self.stream_active[stream]
                else:
                    self.active_block_idx = None
                    self._ensure_active_block()
                    dst_idx = self.active_block_idx
                if dst_idx is None:
                    raise RuntimeError("Allocator inconsistency during GC")
                dst_p = self.blocks[dst_idx].allocate_free_page()
                if dst_p is None:
                    raise RuntimeError("Allocator inconsistency during GC (second)")

            self.blocks[dst_idx].last_prog_step = self._step

            # 원본 무효화(맵에서 지우고 카운트 갱신)
            victim.invalidate_page(p_idx, step=self._step, lam=self.ewma_lambda)
            self.reverse_map.pop((victim_idx, p_idx), None)

            # 새 위치 매핑 및 디바이스 쓰기 카운트
            self.mapping[lpn] = (dst_idx, dst_p)
            self.reverse_map[(dst_idx, dst_p)] = lpn
            self.device_write_pages += 1
            moved_valid += 1

        # victim erase
        freed_before = victim.free_count
        freed_gain = self.pages_per_block - freed_before
        victim.erase()
        self.gc_count += 1
        dt = time.perf_counter() - t0
        self.gc_total_time += dt
        self.gc_durations.append(dt)

        # 이벤트 로그(분석용)
        self.gc_event_log.append({
            "step": self._step,
            "cause": cause,
            "victim": victim_idx,
            "moved_valid": moved_valid,
            "freed_pages": freed_gain,
            "valid_before": valid_before,
            "invalid_before": invalid_before,
            "gc_s": dt,
            "free_blocks_after": self.free_blocks,
        })

    # --- derived ---
    @property
    def total_pages(self) -> int:
        return self.num_blocks * self.pages_per_block

    @property
    def free_pages(self) -> int:
        return sum(b.free_count for b in self.blocks)

    @property
    def free_blocks(self) -> int:
        return sum(1 for b in self.blocks if b.free_count == self.pages_per_block)

    # --- helpers ---
    def _find_block_with_free(self, exclude_idx: Optional[int] = None) -> Optional[int]:
        cands = [i for i, b in enumerate(self.blocks) if b.free_count > 0 and i != exclude_idx]
        return self.rng.choice(cands) if cands else None

    def _ensure_active_block(self) -> None:
        if self.active_block_idx is not None and self.blocks[self.active_block_idx].free_count > 0:
            return
        empties = [i for i, b in enumerate(self.blocks) if b.free_count == self.pages_per_block]
        self.active_block_idx = self.rng.choice(empties) if empties else self._find_block_with_free()

    def _ensure_stream_block(self, stream: str, exclude_idx: Optional[int] = None) -> None:
        idx = self.stream_active.get(stream)
        if idx is not None and self.blocks[idx].free_count > 0:
            return
        empties = [i for i, b in enumerate(self.blocks)
                   if b.free_count == self.pages_per_block and i != exclude_idx]
        chosen = self.rng.choice(empties) if empties else self._find_block_with_free(exclude_idx)
        self.stream_active[stream] = chosen
        if chosen is not None:
            self.blocks[chosen].stream_id = stream

    # --- hotness ---
    def _is_hot_lpn(self, lpn: int) -> bool:
        if self.hotness_mode == "oracle" and self.oracle_hot_cut is not None:
            return lpn < self.oracle_hot_cut
        last = self.lpn_last_write.get(lpn, -10**12)
        return (self._step - last) <= int(self.recency_tau)

    def _alloc_block_for_migration(self, victim_idx: int, lpn: int) -> int:
        """
        GC 마이그레이션 목적지 블록을 고른다.
        기본은 victim 블록의 stream을 보존. (원하면 _is_hot_lpn(lpn)으로 재분류도 가능)
        """
        victim_stream = getattr(self.blocks[victim_idx], "stream_id", "user")
        if self.three_stream:
            # 보존형
            stream = victim_stream
            # # 재분류형(선호 시 주석 해제):
            # stream = "hot" if self._is_hot_lpn(lpn) else victim_stream
            self._ensure_stream_block(stream, exclude_idx=victim_idx)
            dst = self.stream_active[stream]
            if dst is None:
                # 마지막 안전망: 아무 블록이나
                dst = self._find_block_with_free(exclude_idx=victim_idx)
            return dst
        # single-stream fallback
        self._ensure_active_block()
        return self.active_block_idx

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
        self.reverse_map.pop((b, p), None)

    # --- host ops ---
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
            self._ensure_active_block()
            b_idx = self.active_block_idx
        if b_idx is None:
            raise RuntimeError("No free page before GC")

        p_idx = self.blocks[b_idx].allocate_free_page()
        if p_idx is None:
            if self.three_stream:
                self._ensure_stream_block(stream)
                b_idx = self.stream_active[stream]
            else:
                self.active_block_idx = None
                self._ensure_active_block()
                b_idx = self.active_block_idx
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