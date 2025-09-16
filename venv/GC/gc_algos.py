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

def get_gc_policy(name: str):
    if name == "greedy":
        return greedy_policy
    if name == "cb":
        return cb_policy
    raise ValueError(name)
