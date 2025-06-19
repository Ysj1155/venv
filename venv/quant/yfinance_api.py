import yfinance as yf
import pandas as pd
import time
from functools import lru_cache

@lru_cache(maxsize=50)
def get_stock_data(ticker):
    time.sleep(2)
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo", interval="1d")

    if hist.empty:
        return None

    df = hist[["Close"]].rename(columns={"Close": "close"}).copy()
    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()
    # RSI 계산
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df.dropna(inplace=True)
    return df

def get_current_price(ticker):
    stock = yf.Ticker(ticker)
    return stock.info.get("regularMarketPrice", None)
