import os
import argparse
from datetime import datetime
from config import SimConfig
from simulator import Simulator
from workload import make_workload
from metrics import append_summary_csv
import gc_algos

# ------------------------------
# helpers
# ------------------------------

def _resolve_path(path: str, out_dir: str) -> str | None:
    if path is None:
        return None
    return path if os.path.isabs(path) else os.path.join(out_dir, path)


def _infer_user_total_pages(cfg) -> int:
    """
    다양한 SimConfig 형태를 호환해서 user_total_pages(=실험에 쓰는 LPN 수)를 추정.
    우선순위:
      1) cfg.user_total_pages / total_user_pages / ssd_total_pages
      2) (blocks|num_blocks|total_blocks) * (pages_per_block|ppb) * (user_capacity_ratio|capacity_ratio|1.0)
      3) total_pages * (user_capacity_ratio|capacity_ratio|1.0)
    없으면 RuntimeError.
    """
    # 1) 직접 필드
    for attr in ("user_total_pages", "total_user_pages", "ssd_total_pages"):
        v = getattr(cfg, attr, None)
        if isinstance(v, int) and v > 0:
            return v

    # 공통 필드 후보
    blocks = (
        getattr(cfg, "num_blocks", None)
        or getattr(cfg, "blocks", None)
        or getattr(cfg, "total_blocks", None)
    )
    ppb = getattr(cfg, "pages_per_block", None) or getattr(cfg, "ppb", None)
    ratio = (
        getattr(cfg, "user_capacity_ratio", None)
        or getattr(cfg, "capacity_ratio", None)
        or 1.0
    )

    # 2) blocks * ppb * ratio
    try:
        if blocks and ppb:
            return int(int(blocks) * int(ppb) * float(ratio))
    except Exception:
        pass

    # 3) total_pages * ratio
    total_pages = getattr(cfg, "total_pages", None)
    try:
        if total_pages and isinstance(total_pages, int) and total_pages > 0:
            return int(total_pages * float(ratio))
    except Exception:
        pass

    raise RuntimeError(
        "user_total_pages 추정 실패: SimConfig 구조가 예상과 다릅니다. "
        "필요 필드(user_total_pages / (blocks*ppb*ratio) / total_pages)를 확인하세요."
    )


def _inject_policy(args, sim: Simulator):
    """
    args.gc_policy 문자열에 따라 sim.gc_policy를 주입한다.
    now_step이 필요한 정책은 래핑하여 전달.
    CAT 확장 설정(콜드 바이어스/트림 보너스/top-k/가중치)은 gc_algos 전역에 반영.
    """
    name = (args.gc_policy or "").lower()

    # ---- CAT 확장 설정 주입 (있을 때만 안전 적용) ----
    if hasattr(gc_algos, "config_cold_bias"):
        gc_algos.config_cold_bias(args.cold_victim_bias)
    if hasattr(gc_algos, "config_trim_age_bonus"):
        gc_algos.config_trim_age_bonus(args.trim_age_bonus)
    if hasattr(gc_algos, "config_victim_prefetch_k"):
        gc_algos.config_victim_prefetch_k(args.victim_prefetch_k)
    if hasattr(gc_algos, "config_cat_weights"):
        # alpha/beta/gamma/delta 중 None 아닌 것만 반영
        w = dict(alpha=args.cat_alpha, beta=args.cat_beta, gamma=args.cat_gamma, delta=args.cat_delta)
        # None 방지
        w = {k: v for k, v in w.items() if v is not None}
        if w:
            gc_algos.config_cat_weights(**w)

    # ---- 기본 정책들 ----
    if name in ("greedy",):
        sim.gc_policy = getattr(gc_algos, "greedy_policy")
        return

    if name in ("cb", "cost_benefit"):
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
    ap.add_argument("--gc_free_block_threshold", type=float, default=0.12, help="free blocks 비율 임계치 (0~1)")
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

    # CAT 확장 옵션(있을 때만 적용)
    ap.add_argument("--cat_alpha", type=float, default=None, help="CAT α (invalid)")
    ap.add_argument("--cat_beta",  type=float, default=None, help="CAT β (1-hot)")
    ap.add_argument("--cat_gamma", type=float, default=None, help="CAT γ (age)")
    ap.add_argument("--cat_delta", type=float, default=None, help="CAT δ (1-wear)")
    ap.add_argument("--cold_victim_bias", type=float, default=1.0, help="cold 풀 가점(>1.0)")
    ap.add_argument("--trim_age_bonus", type=float, default=0.0, help="TRIM 비율 기반 age 보너스")
    ap.add_argument("--victim_prefetch_k", type=int, default=1, help="victim 후보 top-K")

    # ATCB / RE50315 파라미터
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
    out_csv_path       = _resolve_path(args.out_csv, out_dir) if args.out_csv else None
    trace_csv_path     = _resolve_path(args.trace_csv, out_dir) if args.trace_csv else None
    gc_events_csv_path = _resolve_path(args.gc_events_csv, out_dir) if args.gc_events_csv else None

    # ---- 설정 객체 & 시뮬레이터 ----
    cfg = SimConfig(
        num_blocks=args.blocks,
        pages_per_block=args.pages_per_block,
        gc_free_block_threshold=args.gc_free_block_threshold,
        rng_seed=args.seed,
        user_capacity_ratio=args.user_capacity_ratio,
    )

    # user_total_pages 보정(필드가 없을 수 있어 명시 세팅)
    user_total_pages = _infer_user_total_pages(cfg)
    try:
        setattr(cfg, "user_total_pages", user_total_pages)
    except Exception:
        pass

    sim = Simulator(cfg, enable_trace=bool(trace_csv_path), bg_gc_every=args.bg_gc_every)
    _inject_policy(args, sim)

    # ---- 워크로드 생성 ----
    wl = make_workload(
        n_ops=args.ops,
        update_ratio=args.update_ratio,
        ssd_total_pages=user_total_pages,
        rng_seed=args.seed,
        hot_ratio=args.hot_ratio,
        hot_weight=args.hot_weight,
        enable_trim=args.enable_trim,
        trim_ratio=args.trim_ratio,
    )

    # ---- 워밍업(선행 채우기) ----
    if args.warmup_fill > 0.0:
        # free 블록 2개는 반드시 남기자 (프로젝트에 맞춰 조정 가능)
        reserve_free_blocks = 2
        pages_per_block = getattr(cfg, "pages_per_block", getattr(cfg, "ppb", 64))
        max_warm_pages = max(0, user_total_pages - reserve_free_blocks * pages_per_block)
        target_pages = min(int(user_total_pages * min(max(args.warmup_fill, 0.0), 0.99)), max_warm_pages)

        wrote = 0
        lpn = 0
        while wrote < target_pages and lpn < user_total_pages:
            # free_pages가 0에 근접하면 GC로 숨통 틔움
            if getattr(sim.ssd, "free_pages", 1) <= pages_per_block:
                sim.ssd.collect_garbage(sim.gc_policy, cause="warmup")
            sim.ssd.write_lpn(lpn)
            wrote += 1
            lpn += 1

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