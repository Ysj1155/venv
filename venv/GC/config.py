from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict

# ------------------------------------------------------------
# 실행/장치 설정 — 원본과 인터페이스 유지하며 안전 장치/파생값 추가
# ------------------------------------------------------------

@dataclass
class SimConfig:
    # Geometry
    num_blocks: int = 256
    pages_per_block: int = 64
    user_capacity_ratio: float = 0.9  # 논리 용량(=유저에게 보이는 용량) 비율 (0~1)

    # GC / Randomness
    gc_free_block_threshold: float = 0.12  # free blocks 비율 임계치 (0~1)
    rng_seed: int = 42

    # Latency profile (마이크로초)
    host_prog_us: int = 100   # page program
    host_read_us: int = 50    # page read
    erase_us: int = 1500      # block erase
    migrate_read_prog_us: int = 150  # read+prog 합산(기본값=50+100)

    # 추가 프로파일 프리셋(옵션)
    io_profile: str = "default"  # default|fast|slow|qos_lowlat

    # 내부 캐시(계산 결과)
    _validated: bool = field(default=False, init=False, repr=False)

    # -------- 파생값 --------
    @property
    def total_pages(self) -> int:
        return max(0, int(self.num_blocks) * int(self.pages_per_block))

    @property
    def user_total_pages(self) -> int:
        # 0~1 범위로 클램프
        r = min(max(float(self.user_capacity_ratio), 0.0), 1.0)
        return int(self.total_pages * r)

    @property
    def free_block_threshold_abs(self) -> int:
        # free block 임계치를 절대 개수로 환산
        r = min(max(float(self.gc_free_block_threshold), 0.0), 1.0)
        return int(round(self.num_blocks * r))

    # -------- 유틸 --------
    def validate(self) -> None:
        # geometry
        if self.num_blocks <= 0 or self.pages_per_block <= 0:
            raise ValueError("num_blocks/pages_per_block 는 양수여야 합니다")
        # ratio 범위
        if not (0.0 < self.user_capacity_ratio <= 1.0):
            raise ValueError("user_capacity_ratio 는 (0,1] 범위여야 합니다")
        if not (0.0 <= self.gc_free_block_threshold < 1.0):
            raise ValueError("gc_free_block_threshold 는 [0,1) 범위여야 합니다")
        # latency 양수
        for k in ("host_prog_us","host_read_us","erase_us","migrate_read_prog_us"):
            if getattr(self, k) <= 0:
                raise ValueError(f"{k} 는 양수여야 합니다")
        self._validated = True

    def apply_io_profile(self) -> None:
        """간단한 프리셋으로 지연시간을 오버라이드 (옵션)."""
        p = (self.io_profile or "default").lower()
        if p == "default":
            self.host_read_us = 50
            self.host_prog_us = 100
            self.erase_us = 1500
            self.migrate_read_prog_us = self.host_read_us + self.host_prog_us
        elif p == "fast":
            self.host_read_us = 30
            self.host_prog_us = 70
            self.erase_us = 1000
            self.migrate_read_prog_us = self.host_read_us + self.host_prog_us
        elif p == "slow":
            self.host_read_us = 80
            self.host_prog_us = 160
            self.erase_us = 2500
            self.migrate_read_prog_us = self.host_read_us + self.host_prog_us
        elif p == "qos_lowlat":
            # 읽기 지연 우선 감소, erase는 그대로
            self.host_read_us = 25
            self.host_prog_us = 90
            self.erase_us = 1500
            self.migrate_read_prog_us = self.host_read_us + self.host_prog_us
        else:
            # 알 수 없는 프로파일은 무시
            pass

    def to_dict(self) -> Dict:
        return asdict(self)

    # run 전 안전 초기화용 헬퍼(선택)
    def prepare(self) -> None:
        self.apply_io_profile()
        self.validate()