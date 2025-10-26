# gc_algos.py — safe & unified

# ---------- 공통 헬퍼 ----------
def _block_used(b):
    return int(getattr(b, "valid_count", 0)) + int(getattr(b, "invalid_count", 0))

def _hotness(b):
    # 없으면 0.0(차가움)으로 간주
    return float(getattr(b, "inv_ewma", 0.0))

def _last_activity(b):
    lp = int(getattr(b, "last_prog_step", 0))
    li = int(getattr(b, "last_invalid_step", 0))
    return max(lp, li)

def _wear(b):
    return int(getattr(b, "erase_count", 0))

# ---------- 기본 정책들 ----------
def greedy_policy(blocks):
    """invalid 페이지가 가장 많은 블록을 victim으로"""
    best_idx, best_invalid = None, -1
    for i, b in enumerate(blocks):
        used = _block_used(b)
        if used == 0:
            continue
        inv = int(getattr(b, "invalid_count", 0))
        if inv > best_invalid:
            best_invalid = inv
            best_idx = i
    return best_idx

def cb_policy(blocks):
    """
    Cost-Benefit의 단순 근사:
      score = (1 - u) * age_proxy
      u = valid_ratio, age_proxy = 1 / (1 + erase_count)
    """
    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = _block_used(b)
        if used == 0:
            continue
        u = (getattr(b, "valid_count", 0) / used)
        age_proxy = 1.0 / (1.0 + _wear(b))
        s = (1.0 - u) * age_proxy
        if s > best_score:
            best_score, best_idx = s, i
    return best_idx

def bsgc_policy(blocks, alpha=0.7, beta=0.3):
    """
    score = alpha * invalid_ratio + beta * (1 - wear_norm)
    """
    wears = [_wear(b) for b in blocks]
    max_erase = max(wears) if wears else 0
    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = _block_used(b)
        if used == 0:
            continue
        invalid_ratio = getattr(b, "invalid_count", 0) / used
        wear_norm = (_wear(b) / max_erase) if max_erase > 0 else 0.0
        s = alpha * invalid_ratio + beta * (1.0 - wear_norm)
        if s > best_score:
            best_score, best_idx = s, i
    return best_idx

# ---------- CAT (Cold-Aware with Temperature & Age) ----------
def cat_policy(blocks, alpha=0.55, beta=0.25, gamma=0.15, delta=0.05):
    """
    score = α*invalid_ratio + β*(1-hotness) + γ*age_norm + δ*(1-wear_norm)
    """
    lasts = [_last_activity(b) for b in blocks]
    if not lasts:
        return None
    last_max, last_min = max(lasts), min(lasts)
    age_den = max(1, last_max - last_min)

    wears = [_wear(b) for b in blocks]
    max_erase = max(wears) if wears else 0

    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = _block_used(b)
        if used == 0:
            continue
        invalid_ratio = getattr(b, "invalid_count", 0) / used
        hotness = _hotness(b)
        age_norm = (last_max - _last_activity(b)) / age_den
        wear_norm = (_wear(b) / max_erase) if max_erase > 0 else 0.0
        s = alpha*invalid_ratio + beta*(1.0 - hotness) + gamma*age_norm + delta*(1.0 - wear_norm)
        if s > best_score:
            best_score, best_idx = s, i
    return best_idx

# ---------- ATCB / RE50315 (경량 비교용) ----------
def atcb_policy(blocks, alpha=0.5, beta=0.3, gamma=0.1, eta=0.1, now_step=None):
    """
    score = α*(1-u) + β*(1-wear_norm) + γ*age_norm + η*(1-hotness)
    """
    used_list = [_block_used(b) for b in blocks]
    if not any(used_list):
        return None

    wears = [_wear(b) for b in blocks]
    max_erase = max(wears) if wears else 0

    lasts = [_last_activity(b) for b in blocks]
    last_min = min(lasts) if lasts else 0
    if now_step is None:
        now_step = max(lasts) if lasts else 0
    age_den = max(1, now_step - last_min)

    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = _block_used(b)
        if used == 0:
            continue
        u = getattr(b, "valid_count", 0) / used
        inv = 1.0 - u
        wear_norm = (_wear(b) / max_erase) if max_erase > 0 else 0.0
        age_norm = (now_step - _last_activity(b)) / age_den
        hot = _hotness(b)
        s = alpha*inv + beta*(1.0 - wear_norm) + gamma*age_norm + eta*(1.0 - hot)
        if s > best_score:
            best_score, best_idx = s, i
    return best_idx

def re50315_policy(blocks, K=1.0, now_step=None):
    """
    score = (1-u) + K*age_norm + (1-wear_norm)
    """
    used_list = [_block_used(b) for b in blocks]
    if not any(used_list):
        return None

    wears = [_wear(b) for b in blocks]
    max_erase = max(wears) if wears else 0

    lasts = [_last_activity(b) for b in blocks]
    last_min = min(lasts) if lasts else 0
    if now_step is None:
        now_step = max(lasts) if lasts else 0
    age_den = max(1, now_step - last_min)

    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = _block_used(b)
        if used == 0:
            continue
        u = getattr(b, "valid_count", 0) / used
        inv = 1.0 - u
        wear_norm = (_wear(b) / max_erase) if max_erase > 0 else 0.0
        age_norm = (now_step - _last_activity(b)) / age_den
        s = inv + K*age_norm + (1.0 - wear_norm)
        if s > best_score:
            best_score, best_idx = s, i
    return best_idx

# ---------- 단일 팩토리 (중복 제거) ----------
def get_gc_policy(name: str):
    n = (name or "").lower()
    if n == "greedy":  return greedy_policy
    if n in ("cb", "cost_benefit"): return cb_policy
    if n == "bsgc":    return bsgc_policy
    if n == "cat":     return cat_policy
    if n in ("atcb", "atcb_policy"):
        # 하이퍼파라/now_step은 run_sim.py에서 partial/래핑으로 주입 가능
        return lambda blocks: atcb_policy(blocks)
    if n in ("re50315", "re50315_policy"):
        return lambda blocks: re50315_policy(blocks)
    raise ValueError(f"unknown policy: {name}")