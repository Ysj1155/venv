from enum import Enum
import random
import time

class PageState(Enum):
    FREE = 0
    VALID = 1
    INVALID = 2

class Block:
    def __init__(self, pages_per_block: int):
        self.pages_per_block = pages_per_block
        self.pages = [PageState.FREE] * pages_per_block
        self.valid_count = 0
        self.invalid_count = 0
        self.erase_count = 0
        self.last_invalid_step = 0
        self.last_prog_step = 0          # 마지막 VALID 기록 시점
        self.inv_ewma = 0.0              # 무효 이벤트 EWMA(블록 온도)

    def allocate_free_page(self):
        for idx, st in enumerate(self.pages):
            if st == PageState.FREE:
                self.pages[idx] = PageState.VALID
                self.valid_count += 1
                return idx
        return None

    def invalidate_page(self, page_idx: int, step: int = 0, lam: float = 0.02):
        st = self.pages[page_idx]
        if st == PageState.VALID:
            self.pages[page_idx] = PageState.INVALID
            self.valid_count -= 1
            self.invalid_count += 1
            self.last_invalid_step = step
            # 온도(EWMA) 갱신: 무효 이벤트가 날 때만 1을 섞어줌
            self.inv_ewma = (1.0 - lam) * self.inv_ewma + lam * 1.0

    def erase(self):
        self.pages = [PageState.FREE] * self.pages_per_block
        self.invalid_count = 0
        self.valid_count = 0
        self.erase_count += 1

    @property
    def free_count(self):
        return self.pages_per_block - self.valid_count - self.invalid_count


class SSD:
    def __init__(self, num_blocks: int, pages_per_block: int, rng_seed: int = 42):
        # 파라미터
        self.num_blocks = num_blocks
        self.pages_per_block = pages_per_block
        self.rng = random.Random(rng_seed)

        # 메트릭/상태
        self._step = 0
        self.ewma_lambda = 0.02
        self.host_write_pages = 0
        self.device_write_pages = 0
        self.gc_count = 0
        self.gc_total_time = 0.0
        self.gc_durations = []

        # 매핑
        self.mapping = {}         # LPN -> (b, p)
        self.reverse_map = {}     # (b, p) -> LPN

        # 활성 블록(로그 구조 쓰기)
        self.active_block_idx = None

        # 블록 배열
        self.blocks = [Block(pages_per_block) for _ in range(num_blocks)]

        # per-GC 이벤트 기록
        self.gc_event_log = []

    @property
    def total_pages(self):
        return self.num_blocks * self.pages_per_block

    @property
    def free_pages(self):
        return sum(b.free_count for b in self.blocks)

    @property
    def free_blocks(self):
        return sum(1 for b in self.blocks if b.free_count == self.pages_per_block)

    # --------- 내부 유틸 ----------
    def _find_block_with_free(self, exclude_idx: int = None):
        candidates = [i for i, b in enumerate(self.blocks)
                      if b.free_count > 0 and i != exclude_idx]
        return self.rng.choice(candidates) if candidates else None

    def _ensure_active_block(self):
        """활성 블록 보장: 완전히 빈 블록을 우선 활성화."""
        if self.active_block_idx is not None and self.blocks[self.active_block_idx].free_count > 0:
            return
        empties = [i for i, b in enumerate(self.blocks) if b.free_count == self.pages_per_block]
        if empties:
            self.active_block_idx = self.rng.choice(empties)
        else:
            self.active_block_idx = self._find_block_with_free()

    # --------- 호스트 쓰기 ----------
    def write_lpn(self, lpn: int):
        """호스트 쓰기 1페이지 처리: 기존 VALID 무효화 → 활성 블록에 연속쓰기."""
        self._step += 1

        # 기존 매핑 무효화
        if lpn in self.mapping:
            prev_b, prev_p = self.mapping[lpn]
            self.blocks[prev_b].invalidate_page(prev_p, step=self._step, lam=self.ewma_lambda)
            self.reverse_map.pop((prev_b, prev_p), None)

        # 활성 블록에 쓰기
        self._ensure_active_block()
        b_idx = self.active_block_idx
        if b_idx is None:
            raise RuntimeError("No free page available before GC")

        p_idx = self.blocks[b_idx].allocate_free_page()
        if p_idx is None:
            # 활성 블록이 꽉 찼다면 회전 후 재시도
            self.active_block_idx = None
            self._ensure_active_block()
            b_idx = self.active_block_idx
            if b_idx is None:
                raise RuntimeError("No free page available after rotating active block")
            p_idx = self.blocks[b_idx].allocate_free_page()
            if p_idx is None:
                raise RuntimeError("Allocator inconsistency")

        # 매핑 갱신
        self.mapping[lpn] = (b_idx, p_idx)
        self.reverse_map[(b_idx, p_idx)] = lpn
        # 마지막 프로그램 시각 갱신 (✅ 여기서만 갱신)
        self.blocks[b_idx].last_prog_step = self._step

        # 카운트
        self.host_write_pages += 1
        self.device_write_pages += 1

    def trim_lpn(self, lpn: int):
        """논리 삭제: 매핑 제거 + 물리 페이지 INVALID 처리."""
        if lpn in self.mapping:
            b_idx, p_idx = self.mapping.pop(lpn)
            self.blocks[b_idx].invalidate_page(p_idx, step=self._step, lam=self.ewma_lambda)
            self.reverse_map.pop((b_idx, p_idx), None)

    # --------- GC ----------
    def collect_garbage(self, pick_victim_block_idx, cause: str = "fg_threshold"):
        start = time.perf_counter()
        v_idx = pick_victim_block_idx(self.blocks)
        if v_idx is None:
            return False

        victim = self.blocks[v_idx]
        moved = 0
        valid_before = victim.valid_count
        invalid_before = victim.invalid_count

        # VALID 페이지 마이그레이션
        if victim.valid_count > 0:
            for p_idx, st in enumerate(victim.pages):
                if st == PageState.VALID:
                    lpn = self.reverse_map.get((v_idx, p_idx))
                    if lpn is None:
                        continue
                    nb_idx = self._find_block_with_free(exclude_idx=v_idx)
                    if nb_idx is None:
                        # 기록 후 조기 종료
                        dt = time.perf_counter() - start
                        self.gc_total_time += dt;
                        self.gc_durations.append(dt)
                        self.gc_event_log.append({
                            "step": self._step, "cause": cause, "victim": v_idx,
                            "moved": moved, "valid_before": valid_before, "invalid_before": invalid_before,
                            "duration_ms": dt * 1000.0, "free_pages_after": self.free_pages
                        })
                        return False

                    np_idx = self.blocks[nb_idx].allocate_free_page()
                    if np_idx is None:
                        dt = time.perf_counter() - start
                        self.gc_total_time += dt;
                        self.gc_durations.append(dt)
                        self.gc_event_log.append({
                            "step": self._step, "cause": cause, "victim": v_idx,
                            "moved": moved, "valid_before": valid_before, "invalid_before": invalid_before,
                            "duration_ms": dt * 1000.0, "free_pages_after": self.free_pages
                        })
                        return False

                    self.mapping[lpn] = (nb_idx, np_idx)
                    self.reverse_map[(nb_idx, np_idx)] = lpn
                    del self.reverse_map[(v_idx, p_idx)]
                    self.device_write_pages += 1
                    moved += 1

        victim.erase()
        self.gc_count += 1
        if self.active_block_idx == v_idx:
            self.active_block_idx = None

        dt = time.perf_counter() - start
        self.gc_total_time += dt
        self.gc_durations.append(dt)
        self.gc_event_log.append({
            "step": self._step, "cause": cause, "victim": v_idx,
            "moved": moved, "valid_before": valid_before, "invalid_before": invalid_before,
            "duration_ms": dt * 1000.0, "free_pages_after": self.free_pages
        })
        return True