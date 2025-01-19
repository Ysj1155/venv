# main.py
from data.data_loader import load_data, load_multiple_tickers
from data.data_updater import update_data
from config import OWNED_STOCKS, INTERESTED_STOCKS

def list_owned_stocks():
    print("=== Owned Stocks ===")
    for stock, details in OWNED_STOCKS.items():
        print(f"{stock}: Quantity: {details['quantity']}, Avg Price: ${details['avg_price']}")

def list_interested_stocks():
    print("\n=== Interested Stocks ===")
    for stock in INTERESTED_STOCKS:
        print(stock)

if __name__ == "__main__":
    list_owned_stocks()
    list_interested_stocks()
# 설정
GLOBAL_TICKERS = ['AAPL', '^GSPC', 'MSFT']
KR_TICKERS = ['005930', '000660', '035420']  # 삼성전자, SK하이닉스, 네이버
START_DATE = '2023-01-01'
END_DATE = '2025-01-19'

# 글로벌 시장 데이터 로드
print("Loading global market data...")
load_multiple_tickers(GLOBAL_TICKERS, START_DATE, END_DATE, market="global")

# 한국 시장 데이터 로드
print("Loading Korean market data...")
load_multiple_tickers(KR_TICKERS, START_DATE, END_DATE, market="kr")
