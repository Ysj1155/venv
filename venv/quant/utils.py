import json
import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

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