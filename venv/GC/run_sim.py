import argparse
import os

from config import SimConfig
from simulator import Simulator
from workload import make_workload
from gc_algos import get_gc_policy, atcb_policy
from metrics import summarize_metrics, append_summary_csv, save_trace_csv


def build_paths(args):
    """Return (out_dir, out_csv_path|None, trace_csv_path|None). Create dirs as needed."""
    out_dir = getattr(args, "out_dir", ".") or "."
    os.makedirs(out_dir, exist_ok=True)

    out_csv_path = None
    if getattr(args, "out_csv", None):
        out_csv_path = args.out_csv
        if not os.path.isabs(out_csv_path):
            out_csv_path = os.path.join(out_dir, out_csv_path)

    trace_csv_path = None
    if getattr(args, "trace_csv", None):
        traces_dir = os.path.join(out_dir, "traces")
        os.makedirs(traces_dir, exist_ok=True)
        trace_csv_path = args.trace_csv
        if not os.path.isabs(trace_csv_path):
            trace_csv_path = os.path.join(traces_dir, trace_csv_path)

    return out_dir, out_csv_path, trace_csv_path


def main():
    ap = argparse.ArgumentParser()
    # workload & device
    ap.add_argument("--ops", type=int, default=200_000, help="호스트 write(페이지) 횟수")
    ap.add_argument("--update_ratio", type=float, default=0.8, help="업데이트(덮어쓰기) 비율")
    ap.add_argument("--hot_ratio", type=float, default=0.2)
    ap.add_argument("--hot_weight", type=float, default=0.7)
    ap.add_argument("--blocks", type=int, default=256)
    ap.add_argument("--pages_per_block", type=int, default=64)
    ap.add_argument("--gc_free_block_threshold", type=float, default=0.05, help="free blocks 비율 임계치")
    ap.add_argument("--user_capacity_ratio", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=42)

    # policy
    ap.add_argument("--gc_policy", type=str, default="greedy",
                    choices=["greedy", "cb", "bsgc", "atcb"])
    ap.add_argument("--atcb_alpha", type=float, default=0.5)
    ap.add_argument("--atcb_beta",  type=float, default=0.3)
    ap.add_argument("--atcb_gamma", type=float, default=0.1)
    ap.add_argument("--atcb_eta",   type=float, default=0.1)
    ap.add_argument("--ewma_lambda", type=float, default=0.02)

    # outputs
    ap.add_argument("--out_dir", type=str, default="results")
    ap.add_argument("--out_csv", type=str, default=None)
    ap.add_argument("--trace_csv", type=str, default=None)
    ap.add_argument("--note", type=str, default="")

    ap.add_argument("--bg_gc_every", type=int, default=0, help="K>0이면 매 K ops마다 백그라운드 GC 시도")
    ap.add_argument("--gc_events_csv", type=str, default=None, help="per-GC 이벤트 로그 파일명")

    args = ap.parse_args()

    # ---- paths (safe) ----
    out_dir, out_csv_path, trace_csv_path = build_paths(args)

    # ---- config ----
    cfg = SimConfig(
        num_blocks=args.blocks,
        pages_per_block=args.pages_per_block,
        gc_free_block_threshold=args.gc_free_block_threshold,
        rng_seed=args.seed,
        user_capacity_ratio=args.user_capacity_ratio,
    )

    # ---- simulator & policy injection ----
    # 기본 정책 준비 (ATCB는 아래에서 래핑해서 설정)
    base_policy = get_gc_policy(args.gc_policy if args.gc_policy != "atcb" else "greedy")
    sim = Simulator(cfg, gc_policy=base_policy, enable_trace=bool(trace_csv_path), bg_gc_every=args.bg_gc_every)
    sim.ssd.ewma_lambda = args.ewma_lambda

    # 실행 후 저장:
    if getattr(args, "gc_events_csv", None):
        ev_path = args.gc_events_csv
        if not os.path.isabs(ev_path):
            ev_path = os.path.join(out_dir, ev_path)
        from metrics import save_gc_events_csv
        save_gc_events_csv(ev_path, sim)

    if args.gc_policy == "atcb":
        # now_step은 sim.ssd._step을 사용하여 매 호출 시 최신 값 반영
        def atcb_with_now(blocks, _sim=sim):
            return atcb_policy(
                blocks,
                alpha=args.atcb_alpha, beta=args.atcb_beta,
                gamma=args.atcb_gamma, eta=args.atcb_eta,
                now_step=_sim.ssd._step,
            )
        sim.gc_policy = atcb_with_now

    # ---- workload ----
    wl = make_workload(
        n_ops=args.ops,
        update_ratio=args.update_ratio,
        ssd_total_pages=cfg.user_total_pages,
        rng_seed=args.seed,
        hot_ratio=args.hot_ratio,
        hot_weight=args.hot_weight,
    )

    # ---- run ----
    sim.run(wl)

    # ---- summary/outputs ----
    summarize_metrics(sim)

    if out_csv_path is not None:
        append_summary_csv(
            out_csv_path,
            sim,
            {
                "policy": args.gc_policy,
                "ops": args.ops,
                "update_ratio": args.update_ratio,
                "hot_ratio": args.hot_ratio,
                "hot_weight": args.hot_weight,
                "seed": args.seed,
                "note": args.note,
            },
        )

    if trace_csv_path is not None:
        save_trace_csv(trace_csv_path, sim)

if __name__ == "__main__":
    main()