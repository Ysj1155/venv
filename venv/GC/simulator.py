"""
Simulator — pool-aware allocation, BG-GC cadence, policy adapter (drop-in)

외부 인터페이스는 그대로 `Simulator` 클래스를 유지하면서,
- hot/cold/gen 풀 분리(옵션)
- BG-GC 주기(pool별 cadence)
- 정책 어댑터: gc_algos의 함수형 정책을 바로 연결, top‑K 있으면 활용
- last_prog_step / last_invalid_step 업데이트 훅

필요 최소 구현만 포함(실제 LPN→PPN 매핑/FTL은 프로젝트 기존 코드와 통합하세요).
"""
from __future__ import annotations
from typing import Optional, List, Tuple, Callable
from dataclasses import dataclass
import time

try:
    from models import Device, Block, PageState
except Exception:  # pragma: no cover
    # 가벼운 타입 폴백(런타임에는 실제 models 사용)
    Device = object  # type: ignore
    Block = object   # type: ignore
    class PageState:  # type: ignore
        FREE=0; VALID=1; INVALID=2

# 정책 로딩(함수형)
try:
    from gc_algos import get_gc_policy
    # 선택적으로 cat의 top‑k 도우미가 있으면 사용
    try:
        from gc_algos import cat_policy_topk  # type: ignore
    except Exception:
        cat_policy_topk = None  # type: ignore
except Exception:
    def get_gc_policy(name: str):  # type: ignore
        raise RuntimeError("gc_algos.get_gc_policy() 가 필요합니다")
    cat_policy_topk = None


@dataclass
class BGSchedule:
    every_hot: int = 256
    every_cold: int = 1024


class Simulator:
    def __init__(self,
                 device: Device,
                 policy_name: str = "cat",
                 cold_pool: bool = True,
                 bg: Optional[BGSchedule] = None):
        self.dev: Device = device
        self.ops: int = 0
        self.cold_pool: bool = bool(cold_pool)
        self.bg = bg or BGSchedule()
        self._policy = get_gc_policy(policy_name)  # 함수형(policy(blocks)->idx)

        # 간단 라우터 상태(데모용): 외부에서 바꿔도 됨
        self._last_stream: str = 'gen'  # 'hot'|'cold'|'gen'
        # 시뮬레이터 time step(논리시각)
        self._t: int = 0

        # 메트릭 훅(외부에서 교체 가능)
        self.on_gc: Optional[Callable[[int, int], None]] = None  # (victim_idx, valid_moved)

        # free lists가 비어있다면 초기화 가정
        if hasattr(self.dev, 'free_gen') and not self.dev.free_gen:
            if hasattr(self.dev, 'blocks'):
                n = len(self.dev.blocks)
                self.dev.free_gen = list(range(n))

    # ---------------- Router ----------------
    def choose_stream(self, lpn: int) -> str:
        """외부 또는 실험 코드에서 self._last_stream만 바꿔도 동작.
        여기서는 그대로 반환."""
        return self._last_stream

    # ---------------- Write / Trim ----------------
    def write(self, lpn: int) -> Optional[Tuple[int, int]]:
        stream = self.choose_stream(lpn)
        blk_idx, blk = self._ensure_active_block(stream if self.cold_pool else 'gen')
        ppn = self._allocate_page(blk)
        if ppn is None:
            # 공간 없으면 한 번 GC 시도 → 다시 alloc
            self.gc_once(prefer_pool=stream if self.cold_pool else None)
            ppn = self._allocate_page(blk)
            if ppn is None:
                # 여전히 실패하면 포기(상위에서 재시도)
                return None
        # hotness/age 업데이트
        blk.hot_ewma = 0.9 * float(getattr(blk, 'hot_ewma', 0.0)) + 0.1 * 1.0
        if hasattr(blk, 'age'): blk.age = int(getattr(blk,'age',0)) + 1
        setattr(blk, 'last_prog_step', self._now())

        self.ops += 1
        # BG cadence
        if self.ops % max(1, self.bg.every_hot) == 0:
            self.run_bg_gc(pool='hot')
        if self.ops % max(1, self.bg.every_cold) == 0:
            self.run_bg_gc(pool='cold')
        return (blk_idx, ppn)

    def trim(self, blk_idx: int, page_idx: int) -> bool:
        b = self.dev.blocks[blk_idx]
        if 0 <= page_idx < b.pages_per_block and b.pages[page_idx] == PageState.VALID:
            # invalidate
            b.pages[page_idx] = PageState.INVALID
            b.valid_count = int(getattr(b,'valid_count',0)) - 1
            b.invalid_count = int(getattr(b,'invalid_count',0)) + 1
            b.trimmed_pages = int(getattr(b,'trimmed_pages',0)) + 1
            setattr(b, 'last_invalid_step', self._now())
            return True
        return False

    # ---------------- GC core ----------------
    def gc_once(self, prefer_pool: Optional[str] = None) -> Optional[int]:
        """한 번의 컬렉션을 수행하고 victim 블록 인덱스를 반환."""
        # 후보 집합 준비(필요 시 풀 필터)
        enum = list(enumerate(self.dev.blocks))
        if prefer_pool in ("hot","cold","gen"):
            enum = [(i,b) for i,b in enum if getattr(b,'pool','gen')==prefer_pool]
            if not enum:  # 풀에 후보 없으면 전체로 fallback
                enum = list(enumerate(self.dev.blocks))

        # 함수형 정책이 local 인덱스를 반환하므로 전역 인덱스로 변환 필요
        blocks = [b for _,b in enum]
        if not blocks:
            return None

        # top‑k 지원(선택)
        victim_local_idx: Optional[int]
        if self._policy.__name__ == 'cat_policy' and 'cat_policy_topk' in globals() and cat_policy_topk:
            best_local, topk = cat_policy_topk(blocks, k=1)
            victim_local_idx = best_local
        else:
            victim_local_idx = self._policy(blocks)

        if victim_local_idx is None:
            return None
        victim_global_idx = enum[int(victim_local_idx)][0]
        valid_moved = self._evacuate_and_erase(victim_global_idx)
        if callable(self.on_gc):
            try:
                self.on_gc(victim_global_idx, valid_moved)
            except Exception:
                pass
        return victim_global_idx

    def run_bg_gc(self, pool: Optional[str] = None) -> Optional[int]:
        return self.gc_once(prefer_pool=pool)

    # ---------------- Internals ----------------
    def _now(self) -> int:
        self._t += 1
        return self._t

    def _ensure_active_block(self, stream: str) -> Tuple[int, Block]:
        # Device.ensure_active_block과 역할 유사: 풀에서 블록 가져오기
        # free list 우선, 없으면 빈 블록 스캔
        pick_list_name = {
            'hot': 'free_hot',
            'cold': 'free_cold'
        }.get(stream, 'free_gen')

        flist = getattr(self.dev, pick_list_name, None)
        if isinstance(flist, list) and flist:
            idx = flist.pop()  # LIFO 재사용
            blk = self.dev.blocks[idx]
            blk.pool = stream
            return idx, blk

        # 빈 블록 탐색
        for i, b in enumerate(self.dev.blocks):
            if all(p == PageState.FREE for p in b.pages):
                b.pool = stream
                return i, b

        # 아무 것도 없으면 그냥 가장 적게 마모된 블록 재사용(데모용 fallback)
        wears = [int(getattr(b,'erase_count',0)) for b in self.dev.blocks]
        idx = min(range(len(wears)), key=lambda i: wears[i])
        blk = self.dev.blocks[idx]
        return idx, blk

    def _allocate_page(self, blk: Block) -> Optional[int]:
        for i, s in enumerate(blk.pages):
            if s == PageState.FREE:
                blk.pages[i] = PageState.VALID
                blk.valid_count = int(getattr(blk,'valid_count',0)) + 1
                return i
        return None

    def _evacuate_and_erase(self, idx: int) -> int:
        """유효 페이지를 다른 블록으로 옮기고 victim 블록을 erase.
        여기서는 간단히 유효 카운트만 집계하고, 실제 복사는 생략(프로젝트 원본 로직에 연결 권장).
        """
        b = self.dev.blocks[idx]
        valid = int(getattr(b,'valid_count',0))
        # (실제 구현에서는 유효 페이지를 새 블록에 재기록하고 매핑 업데이트)
        # 블록 erase
        self._erase_block(idx)
        # 풀 복귀
        pool = getattr(b,'pool','gen')
        if pool == 'hot' and hasattr(self.dev,'free_hot'):
            self.dev.free_hot.append(idx)
        elif pool == 'cold' and hasattr(self.dev,'free_cold'):
            self.dev.free_cold.append(idx)
        elif hasattr(self.dev,'free_gen'):
            self.dev.free_gen.append(idx)
        return valid

    def _erase_block(self, idx: int):
        b = self.dev.blocks[idx]
        pages = getattr(b, 'pages_per_block', len(getattr(b,'pages',[])))
        b.pages = [PageState.FREE] * pages
        b.invalid_count = 0
        b.valid_count = 0
        b.trimmed_pages = 0
        b.erase_count = int(getattr(b,'erase_count',0)) + 1
        b.age = 0
        setattr(b, 'last_prog_step', self._now())