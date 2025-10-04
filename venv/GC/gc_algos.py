def greedy_policy(blocks):
    """invalid 페이지가 가장 많은 블록을 victim으로"""
    best_idx, best_invalid = None, -1
    for i, b in enumerate(blocks):
        if b.invalid_count > best_invalid and (b.valid_count + b.invalid_count) > 0:
            best_invalid = b.invalid_count
            best_idx = i
    return best_idx

def cb_policy(blocks):
    """아주 단순화한 Cost-Benefit: 점수 = (1 - u) * age 를 흉내내되 age 부재 → erase_count 적은 블록 가중
    u = valid_ratio, age_proxy = 1/(1+erase_count)
    점수가 큰 블록을 victim
    """
    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = b.valid_count + b.invalid_count
        if used == 0:
            continue
        u = b.valid_count / used
        age_proxy = 1.0 / (1.0 + b.erase_count)
        score = (1.0 - u) * age_proxy
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx

def bsgc_policy(blocks, alpha=0.7, beta=0.3):
    """
    점수 = alpha * invalid_ratio + beta * (1 - erase_norm)
    - invalid_ratio: 무효/사용
    - erase_norm: (해당 블록 erase_count) / (최대 erase_count)
    """
    max_erase = max((b.erase_count for b in blocks), default=0)
    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = b.valid_count + b.invalid_count
        if used == 0:
            continue
        invalid_ratio = b.invalid_count / used
        erase_norm = (b.erase_count / max_erase) if max_erase > 0 else 0.0
        score = alpha * invalid_ratio + beta * (1.0 - erase_norm)
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx

def get_gc_policy(name: str):
    if name == "greedy":
        return greedy_policy
    if name == "cb":
        return cb_policy
    if name == "bsgc":
        return bsgc_policy
    raise ValueError(name)

def atcb_policy(blocks, alpha=0.5, beta=0.3, gamma=0.1, eta=0.1, now_step: int = 0):
    # 보조 통계
    max_erase = max((b.erase_count for b in blocks), default=0)
    max_age   = 1  # 0 division 방지용 기본값
    # age 근사: 최근 활동(프로그램/무효) 이후 경과
    ages = []
    for b in blocks:
        last = max(b.last_prog_step, b.last_invalid_step)
        ages.append(now_step - last)
    if ages:
        max_age = max(ages) or 1

    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = b.valid_count + b.invalid_count
        if used == 0:
            continue
        inv_ratio = b.invalid_count / used
        hot = b.inv_ewma
        wear_norm = (b.erase_count / max_erase) if max_erase > 0 else 0.0
        last = max(b.last_prog_step, b.last_invalid_step)
        age_norm = (now_step - last) / max_age

        score = (
            alpha * inv_ratio +
            beta  * (1.0 - hot) +
            gamma * (1.0 - wear_norm) +
            eta   * age_norm
        )
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx

def get_gc_policy(name: str):
    if name == "greedy":
        return greedy_policy
    if name == "cb":
        return cb_policy
    if name == "bsgc":
        return bsgc_policy
    if name == "atcb":
        # 람다를 캡처한 클로저를 리턴하거나, run_sim.py에서 partial로 넘겨도 OK
        # 여기서는 기본 하이퍼로 단순 연결(가중치는 run_sim.py에서 주입 가능)
        return lambda blocks: atcb_policy(blocks)
    raise ValueError(name)
