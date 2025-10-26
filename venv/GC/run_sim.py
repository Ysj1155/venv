import os
import argparse
from datetime import datetime
from config import SimConfig
from simulator import Simulator
from workload import make_workload
from metrics import append_summary_csv
import gc_algos

def _resolve_path(path: str, out_dir: str) -> str:
    if path is None:
        return None
    return path if os.path.isabs(path) else os.path.join(out_dir, path)

def _inject_policy(args, sim: Simulator):
    """
    args.gc_policy 문자열에 따라 sim.gc_policy를 주입한다.
    now_step이 필요한 정책은 래핑하여 전달.
    """
    name = (args.gc_policy or "").lower()

    # ---- 기본 정책들 ----
    if name in ("greedy",):
        sim.gc_policy = getattr(gc_algos, "greedy_policy")
        return

    if name in ("cb", "cost_benefit"):
        # 파일 내 실제 구현 이름은 cb_policy
        sim.gc_policy = getattr(gc_algos, "cb_policy")
        return

    if name in ("bsgc",):
        sim.gc_policy = getattr(gc_algos, "bsgc_policy")
        return

    if name in ("cat",):
        sim.gc_policy = getattr(gc_algos, "cat_policy")
        return

    # ---- 확장 정책들 (atcb / re50315) ----
    if name in ("atcb", "atcb_policy"):
        atcb_policy = getattr(gc_algos, "atcb_policy", None)
        if atcb_policy is None:
            raise RuntimeError("gc_algos.atcb_policy 가 없습니다. gc_algos.py 를 업데이트하세요.")
        def atcb_with_now(blocks, _sim=sim):
            return atcb_policy(
                blocks,
                alpha=args.atcb_alpha, beta=args.atcb_beta,
                gamma=args.atcb_gamma, eta=args.atcb_eta,
                now_step=_sim.ssd._step,
            )
        sim.gc_policy = atcb_with_now
        return

    if name in ("re50315", "re50315_policy"):
        re50315_policy = getattr(gc_algos, "re50315_policy", None)
        if re50315_policy is None:
            raise RuntimeError("gc_algos.re50315_policy 가 없습니다. gc_algos.py 를 업데이트하세요.")
        def p_with_now(blocks, _sim=sim):
            return re50315_policy(blocks, K=args.re50315_K, now_step=_sim.ssd._step)
        sim.gc_policy = p_with_now
        return

    raise ValueError(f"지원하지 않는 GC 정책: {args.gc_policy}")

def main():
    ap = argparse.ArgumentParser(description="GC simulator runner (drop-in)")
    # ---- 시뮬레이션/장치 파라미터 ----
    ap.add_argument("--ops", type=int, default=200_000, help="호스트 write(페이지) 횟수")
    ap.add_argument("--update_ratio", type=float, default=0.8, help="업데이트(덮어쓰기) 비율 (0~1)")
    ap.add_argument("--hot_ratio", type=float, default=0.2, help="핫 데이터 비율 (0~1)")
    ap.add_argument("--hot_weight", type=float, default=0.7, help="핫 주소로 보낼 가중치 (0~1)")
    ap.add_argument("--blocks", type=int, default=256)
    ap.add_argument("--pages_per_block", type=int, default=64)
    ap.add_argument("--gc_free_block_threshold", type=float, default=0.05, help="free blocks 비율 임계치 (0~1)")
    ap.add_argument("--user_capacity_ratio", type=float, default=0.9, help="유저 영역 비율 (0~1)")
    ap.add_argument("--seed", type=int, default=42)

    # ---- TRIM & WARMUP ----
    ap.add_argument("--enable_trim", action="store_true", help="워크로드에 TRIM 포함")
    ap.add_argument("--trim_ratio", type=float, default=0.0, help="TRIM 확률(0~1)")
    ap.add_argument("--warmup_fill", type=float, default=0.0,
                    help="실행 전 선행 채우기 비율(0.0~0.99). steady-state 비교용")

    # ---- 정책 선택 & 파라미터 ----
    ap.add_argument("--gc_policy", type=str, default="greedy",
                    choices=["greedy", "cb", "cost_benefit", "bsgc", "cat", "atcb", "re50315"],
                    help="GC 정책 선택")
    ap.add_argument("--atcb_alpha", type=float, default=0.5)
    ap.add_argument("--atcb_beta",  type=float, default=0.3)
    ap.add_argument("--atcb_gamma", type=float, default=0.1)
    ap.add_argument("--atcb_eta",   type=float, default=0.1)
    ap.add_argument("--re50315_K",  type=float, default=1.0)

    # ---- 실행/출력 관련 ----
    ap.add_argument("--bg_gc_every", type=int, default=0,
                    help="K>0이면 매 K ops마다 백그라운드 GC 시도(시뮬레이터가 지원할 때)")
    ap.add_argument("--out_dir", type=str, default="results/run",
                    help="결과/로그를 저장할 디렉토리(상대 경로면 자동 생성)")
    ap.add_argument("--out_csv", type=str, default=None, help="요약 CSV append 경로")
    ap.add_argument("--trace_csv", type=str, default=None, help="옵션: trace CSV (시뮬레이터가 지원 시)")
    ap.add_argument("--gc_events_csv", type=str, default=None, help="per-GC 이벤트 로그 CSV (실행 후 저장)")
    ap.add_argument("--note", type=str, default="", help="메모/주석")
    args = ap.parse_args()

    # ---- 출력 경로 준비 ----
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    out_csv_path      = _resolve_path(args.out_csv, out_dir) if args.out_csv else None
    trace_csv_path    = _resolve_path(args.trace_csv, out_dir) if args.trace_csv else None
    gc_events_csv_path= _resolve_path(args.gc_events_csv, out_dir) if args.gc_events_csv else None

    # ---- 설정 객체 & 시뮬레이터 ----
    cfg = SimConfig(
        num_blocks=args.blocks,
        pages_per_block=args.pages_per_block,
        gc_free_block_threshold=args.gc_free_block_threshold,
        rng_seed=args.seed,
        user_capacity_ratio=args.user_capacity_ratio,
    )
    sim = Simulator(cfg, gc_policy=lambda b: 0, enable_trace=bool(trace_csv_path), bg_gc_every=args.bg_gc_every)
    _inject_policy(args, sim)

    # ---- 워크로드 생성 ----
    wl = make_workload(
        n_ops=args.ops,
        update_ratio=args.update_ratio,
        ssd_total_pages=cfg.user_total_pages,
        rng_seed=args.seed,
        hot_ratio=args.hot_ratio,
        hot_weight=args.hot_weight,
        enable_trim=args.enable_trim,
        trim_ratio=args.trim_ratio,
    )

    # ---- 워밍업(선행 채우기) ----
    if args.warmup_fill > 0.0:
        warm_ops = int(cfg.user_total_pages * min(max(args.warmup_fill, 0.0), 0.99))
        from workload import make_workload as _mw
        warm = _mw(n_ops=warm_ops, update_ratio=0.0, ssd_total_pages=cfg.user_total_pages, rng_seed=args.seed)
        sim.run(warm)

    # ---- 실행 ----
    sim.run(wl)

    # ---- 결과 CSV/로그 저장(가능할 때만) ----
    if out_csv_path:
        meta = {
            "run_id": args.note or f"{args.gc_policy}_{args.seed}",
            "policy": args.gc_policy,
            "ops": args.ops,
            "update_ratio": args.update_ratio,
            "hot_ratio": args.hot_ratio,
            "hot_weight": args.hot_weight,
            "seed": args.seed,
            "trim_enabled": 1 if args.enable_trim else 0,
            "trim_ratio": args.trim_ratio,
            "warmup_fill": args.warmup_fill,
            "bg_gc_every": args.bg_gc_every,
            "note": args.note,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        append_summary_csv(out_csv_path, sim, meta)

    # trace
    if trace_csv_path and getattr(sim, "trace", None):
        import csv
        with open(trace_csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["step","free_pages","device_writes","gc_count","gc_event"])
            for i in range(len(sim.trace["step"])):
                w.writerow([
                    sim.trace["step"][i],
                    sim.trace["free_pages"][i],
                    sim.trace["device_writes"][i],
                    sim.trace["gc_count"][i],
                    sim.trace["gc_event"][i],
                ])

    # per-GC 이벤트
    if gc_events_csv_path and getattr(sim.ssd, "gc_event_log", None):
        import csv
        with open(gc_events_csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=sorted(sim.ssd.gc_event_log[0].keys()))
            w.writeheader()
            for ev in sim.ssd.gc_event_log:
                w.writerow(ev)

if __name__ == "__main__":
    main()