import requests
import time
import pandas as pd
from config import FINNHUB_API_KEY

BASE_URL = "https://finnhub.io/api/v1"

def get_quote(ticker):
    url = f"{BASE_URL}/quote"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    res = requests.get(url, params=params).json()
    return {
        "current": res.get("c"),
        "high": res.get("h"),
        "low": res.get("l"),
        "open": res.get("o"),
        "prev_close": res.get("pc")
    }

def get_candle_data(ticker, days=90):
    now = int(time.time())
    past = now - 60 * 60 * 24 * days
    res = requests.get(f"{BASE_URL}/stock/candle", params={
        "symbol": ticker,
        "resolution": "D",
        "from": past,
        "to": now,
        "token": FINNHUB_API_KEY
    }).json()
    if res.get("s") != "ok":
        return None
    df = pd.DataFrame({
        "timestamp": res["t"],
        "close": res["c"]
    })
    df["date"] = pd.to_datetime(df["timestamp"], unit="s")
    return df

def calculate_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df["RSI"] = rsi
    return df