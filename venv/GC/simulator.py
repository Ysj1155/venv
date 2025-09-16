from models import SSD
from math import ceil

class Simulator:
    def __init__(self, cfg, gc_policy):
        self.cfg = cfg
        self.ssd = SSD(cfg.num_blocks, cfg.pages_per_block, rng_seed=cfg.rng_seed)
        self.gc_policy = gc_policy

    def _need_gc(self):
        # free blocks 비율 기준으로 GC 트리거
        fb_ratio = self.ssd.free_blocks / self.ssd.num_blocks
        return fb_ratio <= self.cfg.gc_free_block_threshold

    def run(self, workload):
        for lpn in workload:
            # 쓰기 전 free 부족하면 선행 GC
            while self._need_gc():
                did = self.ssd.collect_garbage(self.gc_policy)
                if not did:
                    break
            # 호스트 쓰기
            # 드물게 free page가 완전 바닥인 경우 한 번 더 GC
            if self.ssd.free_pages == 0:
                self.ssd.collect_garbage(self.gc_policy)
            self.ssd.write_lpn(lpn)
        # 마지막에도 한 번 정리 GC 돌려 보고 싶으면 옵션으로 가능
