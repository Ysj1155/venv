import argparse
from config import SimConfig
from simulator import Simulator
from workload import make_workload
from gc_algos import get_gc_policy
from metrics import summarize_metrics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=256)
    ap.add_argument("--pages_per_block", type=int, default=64)
    ap.add_argument("--gc_policy", type=str, default="greedy", choices=["greedy","cb"])
    ap.add_argument("--ops", type=int, default=200_000, help="호스트 write(페이지) 횟수")
    ap.add_argument("--update_ratio", type=float, default=0.8, help="업데이트(덮어쓰기) 비율")
    ap.add_argument("--gc_free_block_threshold", type=float, default=0.05, help="free blocks 비율 임계치")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cfg = SimConfig(
        num_blocks=args.blocks,
        pages_per_block=args.pages_per_block,
        gc_free_block_threshold=args.gc_free_block_threshold,
        rng_seed=args.seed
    )

    sim = Simulator(cfg, gc_policy=get_gc_policy(args.gc_policy))
    wl = make_workload(n_ops=args.ops, update_ratio=args.update_ratio, ssd_total_pages=cfg.total_pages, rng_seed=args.seed)
    sim.run(wl)

    summarize_metrics(sim)

if __name__ == "__main__":
    main()