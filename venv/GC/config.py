from dataclasses import dataclass

@dataclass
class SimConfig:
    num_blocks: int = 256
    pages_per_block: int = 64
    gc_free_block_threshold: float = 0.05  # free blocks 비율이 이보다 낮으면 GC 트리거
    rng_seed: int = 42

    @property
    def total_pages(self) -> int:
        return self.num_blocks * self.pages_per_block
