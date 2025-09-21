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
        self.last_invalid_step = 0  # 선택적: 정책 고도화용

    def allocate_free_page(self):
        for idx, st in enumerate(self.pages):
            if st == PageState.FREE:
                self.pages[idx] = PageState.VALID
                self.valid_count += 1
                return idx
        return None

    def invalidate_page(self, page_idx: int, step: int = 0):
        st = self.pages[page_idx]
        if st == PageState.VALID:
            self.pages[page_idx] = PageState.INVALID
            self.valid_count -= 1
            self.invalid_count += 1
            self.last_invalid_step = step

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
        self.num_blocks = num_blocks
        self.pages_per_block = pages_per_block
        self.blocks = [Block(pages_per_block) for _ in range(num_blocks)]
        self.rng = random.Random(rng_seed)

        # 매핑
        self.mapping = {}                 # LPN -> (b, p)
        self.reverse_map = {}             # (b, p) -> LPN

        # 활성 블록(로그 구조 쓰기)
        self.active_block_idx = None

        # 메트릭
        self.host_write_pages = 0
        self.device_write_pages = 0  # 유효 페이지 마이그레이션 포함
        self.gc_count = 0
        self._step = 0

        # GC 시간 측정
        self.gc_total_time = 0.0          # seconds
        self.gc_durations = []            # list[seconds]

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
        """활성 블록 보장: 완전히 비어있는 블록을 우선 활성화."""
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
            b_idx, p_idx = self.mapping[lpn]
            self.blocks[b_idx].invalidate_page(p_idx, step=self._step)
            self.reverse_map.pop((b_idx, p_idx), None)

        # 활성 블록에 쓰기
        self._ensure_active_block()
        b_idx = self.active_block_idx
        if b_idx is None:
            raise RuntimeError("No free page available before GC")

        p_idx = self.blocks[b_idx].allocate_free_page()
        if p_idx is None:
            # 활성 블록이 꽉 찼다면 회전
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

        # 카운트
        self.host_write_pages += 1
        self.device_write_pages += 1

    # --------- GC ----------
    def collect_garbage(self, pick_victim_block_idx):
        """victim 선택 정책으로 블록 하나 GC 수행.
        VALID 페이지는 다른 블록으로 복사(=device writes 증가), 이후 erase.
        수행 시간(초)을 계측해 누적 저장.
        """
        start = time.perf_counter()

        v_idx = pick_victim_block_idx(self.blocks)
        if v_idx is None:
            return False

        victim = self.blocks[v_idx]

        # VALID 페이지 마이그레이션
        if victim.valid_count > 0:
            for p_idx, st in enumerate(victim.pages):
                if st == PageState.VALID:
                    lpn = self.reverse_map.get((v_idx, p_idx))
                    if lpn is None:
                        continue

                    nb_idx = self._find_block_with_free(exclude_idx=v_idx)
                    if nb_idx is None:
                        # 여유가 전혀 없다면 GC 타이밍 문제
                        dt = time.perf_counter() - start
                        self.gc_total_time += dt
                        self.gc_durations.append(dt)
                        return False

                    np_idx = self.blocks[nb_idx].allocate_free_page()
                    if np_idx is None:
                        dt = time.perf_counter() - start
                        self.gc_total_time += dt
                        self.gc_durations.append(dt)
                        return False

                    # 매핑 갱신
                    self.mapping[lpn] = (nb_idx, np_idx)
                    self.reverse_map[(nb_idx, np_idx)] = lpn
                    # 기존 위치 제거
                    del self.reverse_map[(v_idx, p_idx)]

                    self.device_write_pages += 1

        # victim erase
        victim.erase()
        self.gc_count += 1

        # 활성 블록이 victim이었다면 초기화
        if self.active_block_idx == v_idx:
            self.active_block_idx = None

        dt = time.perf_counter() - start
        self.gc_total_time += dt
        self.gc_durations.append(dt)
        return True