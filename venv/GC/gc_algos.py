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

# ---- CAT: Cold-Aware with Temperature & Age ----
def cat_policy(blocks, alpha=0.55, beta=0.25, gamma=0.15, delta=0.05):
    """
    CAT (Cold-Aware with Temperature & Age)

    score = alpha * invalid_ratio            # 회수 효율
          + beta  * (1 - hotness)            # 최근 더러워지지 않은(차가운) 블록 선호
          + gamma * age_norm                 # 최근 활동이 오래된(식은) 블록 선호
          + delta * (1 - wear_norm)          # 과마모 블록 회피

    - invalid_ratio = invalid / (valid+invalid)
    - hotness       = b.inv_ewma
    - age_norm      = (last_max - last_i) / (last_max - last_min + ε)
                      (last_i = max(last_prog_step, last_invalid_step))
    - wear_norm     = b.erase_count / max_erase
    """
    # 스냅샷 기반 정규화(이 구조에선 now_step 전달이 없으므로 last 시각의 상대값으로 계산)
    lasts = [max(b.last_prog_step, b.last_invalid_step) for b in blocks]
    if not lasts:
        return None
    last_max = max(lasts)
    last_min = min(lasts)
    age_den  = max(1, last_max - last_min)

    max_erase = max((b.erase_count for b in blocks), default=0)

    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = b.valid_count + b.invalid_count
        if used == 0:
            continue
        invalid_ratio = b.invalid_count / used
        hotness = b.inv_ewma
        last_i = max(b.last_prog_step, b.last_invalid_step)
        age_norm = (last_max - last_i) / age_den
        wear_norm = (b.erase_count / max_erase) if max_erase > 0 else 0.0

        score = (
            alpha * invalid_ratio +
            beta  * (1.0 - hotness) +
            gamma * age_norm +
            delta * (1.0 - wear_norm)
        )
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx

def cat_components(block):
    # 예시: invalid ratio / recency / stream 일치도 / zero-copy 가능성 등을 0~1로 정규화
    ppb = block.pages_per_block
    inv_ratio = block.invalid_count / ppb
    # 예: 오래된(valid 적고 invalid 많은) 블록 선호 => a = inv_ratio
    a = inv_ratio

    # 예: 최근에 invalidate 많이 발생(EWMA 높음) => 뜨거움 → 지금은 이주비용 클 수 있음
    # CAT에서는 '지금 건드리면 손해'를 점수에 반영하도록 b를 (1 - inv_ewma) 로 둘 수도
    b = 1.0 - min(1.0, block.inv_ewma)

    # 예: 스트림 일관성(피해자와 같은 stream을 유지하면 ZGC 기대치↑). victim에서 쓰니 g는 1.0로 둠.
    # score_probe에서는 '가정적'이므로 g=1.0(보존형)으로 두고, 실제 라우팅과 맞물려 해석.
    g = 1.0

    # 예: zero-copy 기대. valid_count가 0에 가까울수록 이익 큼 → d = 1 - valid_ratio
    vratio = block.valid_count / ppb if ppb>0 else 0
    d = 1.0 - vratio
    return a, b, g, d

def make_cat_probe(alpha, beta, gamma, delta):
    def _probe(blocks):
        out = {}
        for i, blk in enumerate(blocks):
            a,b,g,d = cat_components(blk)
            score = alpha*a + beta*b + gamma*g + delta*d
            out[i] = {"a":a,"b":b,"g":g,"d":d,"score":score}
        return out
    return _probe

def get_gc_policy(name: str):
    name = name.lower()
    if name == "greedy":  return greedy_policy
    if name == "cb":      return cb_policy
    if name == "bsgc":    return bsgc_policy
    if name == "cat":     return cat_policy
    if name == "atcb":
        # 하이퍼파라미터/now_step은 run_sim 또는 호출부에서 래핑하여 주입
        return lambda blocks: atcb_policy(blocks)
    if name == "re50315":
        try:
            return lambda blocks: re50315_policy(blocks)
        except NameError:
            raise ValueError("re50315 policy not available in this build")
    raise ValueError(f"unknown policy: {name}")

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

# --- ADD: patent-like policy ---
def re50315_policy(blocks, K: float = 100.0, now_step: int = 0):
    """
    Patent-inspired: rank = staleness * (age + K)
    - staleness: invalid_count
    - age: now_step - last_activity (last of program/invalid)
    """
    best_idx, best_score = None, float("-inf")
    for i, b in enumerate(blocks):
        used = b.valid_count + b.invalid_count
        if used == 0:
            continue
        staleness = b.invalid_count
        last = max(b.last_prog_step, b.last_invalid_step)
        age = max(0, now_step - last)
        score = staleness * (age + K)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx
