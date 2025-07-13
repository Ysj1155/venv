import json

WATCHLIST_PATH = "watchlist.json"

def load_watchlist_file():
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_watchlist_file(watchlist):
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

def parse_kis_ohlc(data):
    items = data.get("output2", [])
    ohlc = []
    for item in reversed(items):  # 날짜 오름차순
        date = item.get("xymd")
        open_ = item.get("open")
        high = item.get("high")
        low = item.get("low")
        close = item.get("clos")
        volume = item.get("tvol")

        if None in (date, open_, high, low, close, volume):
            continue

        try:
            ohlc.append({
                "date": date,
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": int(volume)
            })
        except (ValueError, TypeError):
            continue
    return ohlc