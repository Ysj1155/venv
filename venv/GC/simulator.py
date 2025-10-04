from models import SSD
from math import ceil

class Simulator:
    def __init__(self, cfg, gc_policy, enable_trace: bool = False, bg_gc_every:int=0):
        self.cfg = cfg
        self.ssd = SSD(cfg.num_blocks, cfg.pages_per_block, rng_seed=cfg.rng_seed)
        self.gc_policy = gc_policy
        self.enable_trace = enable_trace
        self.bg_gc_every = max(0, int(bg_gc_every))  # 0이면 비활성
        self._bg_counter = 0
        self.trace = {"step": [], "free_pages": [], "device_writes": [], "gc_count": [], "gc_event": []}

    def _need_gc(self):
        fb_ratio = self.ssd.free_blocks / self.ssd.num_blocks
        return fb_ratio <= self.cfg.gc_free_block_threshold

    def _maybe_trace(self, pre_gc):
        if self.enable_trace:
            self.trace["step"].append(self.ssd._step)
            self.trace["free_pages"].append(self.ssd.free_pages)
            self.trace["device_writes"].append(self.ssd.device_write_pages)
            self.trace["gc_count"].append(self.ssd.gc_count)
            self.trace["gc_event"].append(1 if self.ssd.gc_count > pre_gc else 0)

    def run(self, workload):
        for op in workload:
            kind, lpn = (op if isinstance(op, tuple) else ("write", op))

            # ---- 포그라운드 GC (임계치) ----
            if self._need_gc():
                self.ssd.collect_garbage(self.gc_policy, cause="fg_threshold")

            pre_gc = self.ssd.gc_count

            # ---- 호스트 요청 처리 ----
            if kind == "trim":
                self.ssd.trim_lpn(lpn)
            else:
                if self.ssd.free_pages == 0:  # 안전망
                    self.ssd.collect_garbage(self.gc_policy, cause="fg_nofree")
                self.ssd.write_lpn(lpn)

            self._maybe_trace(pre_gc)

            # ---- 백그라운드 GC (토큰버킷: every K ops) ----
            if self.bg_gc_every > 0:
                self._bg_counter += 1
                if self._bg_counter >= self.bg_gc_every:
                    # free가 넉넉할 때만 조심스럽게 수행
                    if not self._need_gc() and self.ssd.free_blocks > 1:
                        self.ssd.collect_garbage(self.gc_policy, cause="bg_token")
                    self._bg_counter = 0