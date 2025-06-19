# test_finnhub.py
import time
from finnhub_api import get_quote, get_rsi

ticker = "AAPL"
now = int(time.time())
three_months_ago = now - 60 * 60 * 24 * 90

quote = get_quote(ticker)
rsi = get_rsi(ticker, three_months_ago, now)

print("현재가 정보:", quote)
print("RSI:", rsi)
