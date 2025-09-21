from models import SSD
from math import ceil

class Simulator:
    def __init__(self, cfg, gc_policy):
        self.cfg = cfg
        self.ssd = SSD(cfg.num_blocks, cfg.pages_per_block, rng_seed=cfg.rng_seed)
        self.gc_policy = gc_policy

    def _need_gc(self):
        fb_ratio = self.ssd.free_blocks / self.ssd.num_blocks
        return fb_ratio <= self.cfg.gc_free_block_threshold

    def run(self, workload):
        for lpn in workload:
            # ✅ 한 번의 호스트 쓰기 전에 최대 1회만 GC
            if self._need_gc():
                self.ssd.collect_garbage(self.gc_policy)

            # 남은 free 페이지가 0이면 안전하게 한 번 더
            if self.ssd.free_pages == 0:
                self.ssd.collect_garbage(self.gc_policy)

            # 호스트 쓰기 수행
            self.ssd.write_lpn(lpn)