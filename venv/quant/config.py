import os
from dotenv import load_dotenv

# .env 파일을 로드
load_dotenv()

# 환경변수에서 API 키 불러오기
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if FINNHUB_API_KEY is None:
    raise ValueError("❌ FINNHUB_API_KEY가 .env에서 로드되지 않았습니다.")