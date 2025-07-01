import os
from dotenv import load_dotenv

load_dotenv()

# 환경 변수만 로드
APP_KEY = os.getenv("appkey")
APP_SECRET = os.getenv("secretkey")
ACCOUNT_NO = os.getenv("account")
HTS_ID = os.getenv("id")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 예외처리
if not FINNHUB_API_KEY:
    raise ValueError("❌ FINNHUB_API_KEY가 .env에서 로드되지 않았습니다.")
