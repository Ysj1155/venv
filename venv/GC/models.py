from enum import Enum
import random

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

    def allocate_free_page(self):
        for idx, st in enumerate(self.pages):
            if st == PageState.FREE:
                self.pages[idx] = PageState.VALID
                self.valid_count += 1
                return idx
        return None  # no free page

    def invalidate_page(self, page_idx: int):
        st = self.pages[page_idx]
        if st == PageState.VALID:
            self.pages[page_idx] = PageState.INVALID
            self.valid_count -= 1
            self.invalid_count += 1

    def erase(self):
        # block erase: 모든 페이지 FREE로 초기화
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
        # LPN(Logical Page Number) -> (block_idx, page_idx)
        self.mapping = {}
        # metrics
        self.host_write_pages = 0
        self.device_write_pages = 0  # 유효 페이지 복사 포함
        self.gc_count = 0

    @property
    def total_pages(self):
        return self.num_blocks * self.pages_per_block

    @property
    def free_pages(self):
        return sum(b.free_count for b in self.blocks)

    @property
    def free_blocks(self):
        return sum(1 for b in self.blocks if b.free_count == self.pages_per_block)

    def _find_block_with_free(self):
        # 간단한 라운드로빈/랜덤: 성능 연구 전까지는 랜덤으로 배치
        candidates = [i for i, b in enumerate(self.blocks) if b.free_count > 0]
        return self.rng.choice(candidates) if candidates else None

    def write_lpn(self, lpn: int):
        """호스트 쓰기 1페이지 처리 (기존 매핑 무효화 + 새 위치에 VALID 기록)"""
        # 기존 매핑이 있으면 INVALID 처리
        if lpn in self.mapping:
            b_idx, p_idx = self.mapping[lpn]
            self.blocks[b_idx].invalidate_page(p_idx)

        # 새 페이지 할당
        b_idx = self._find_block_with_free()
        if b_idx is None:
            raise RuntimeError("No free page available before GC")

        p_idx = self.blocks[b_idx].allocate_free_page()
        if p_idx is None:
            raise RuntimeError("Allocator inconsistency")

        self.mapping[lpn] = (b_idx, p_idx)

        # 카운트: 호스트 쓰기 1페이지, 디바이스 쓰기도 1페이지 증가
        self.host_write_pages += 1
        self.device_write_pages += 1

    def collect_garbage(self, pick_victim_block_idx):
        """victim block 선택 함수(정책)로 블록 하나를 GC.
        - 유효 페이지는 다른 블록의 free page로 복사(=device writes 증가)
        - victim 블록 erase
        """
        v_idx = pick_victim_block_idx(self.blocks)
        if v_idx is None:
            return False

        victim = self.blocks[v_idx]
        # 1) 유효 페이지 이동
        if victim.valid_count > 0:
            for p_idx, st in enumerate(victim.pages):
                if st == PageState.VALID:
                    # 읽어서(모델에서는 비용 무시), 새 위치에 쓰고 매핑 갱신
                    nb_idx = self._find_block_with_free()
                    if nb_idx is None or (nb_idx == v_idx and victim.free_count == 0):
                        # 이론상 희박하지만 방어적으로 한 번 더 찾아보기
                        nb_idx = self._find_block_with_free()
                        if nb_idx is None:
                            raise RuntimeError("No free page for migration")
                    np_idx = self.blocks[nb_idx].allocate_free_page()
                    # 매핑 업데이트: 어떤 LPN이었는지 찾아야 함
                    # 역매핑이 없으니 선형탐색은 비효율 -> 실제 구현에선 reverse map 유지 권장
                    # 간단화를 위해 reverse map 유지
                    # (다음 버전에서 개선)
                    # 여기서는 mapping을 뒤져서 v_idx,p_idx를 찾음 (학습용 간단 구현)
                    for lpn_k, (bb, pp) in self.mapping.items():
                        if bb == v_idx and pp == p_idx:
                            self.mapping[lpn_k] = (nb_idx, np_idx)
                            break
                    self.device_write_pages += 1  # 유효 페이지 복사 쓰기

        # 2) victim erase
        victim.erase()
        self.gc_count += 1
        return True
