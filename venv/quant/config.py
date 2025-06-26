import os
from dotenv import load_dotenv

load_dotenv()
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if not FINNHUB_API_KEY:
    raise ValueError("❌ FINNHUB_API_KEY가 .env에서 로드되지 않았습니다.")
