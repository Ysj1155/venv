import yfinance as yf

def get_current_price(ticker):
    """
    특정 주식의 현재 주가를 반환합니다.
    Args:
        ticker (str): 주식 티커.
    Returns:
        float: 현재 주가.
    """
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.history(period="1d")["Close"].iloc[-1]
        return current_price
    except Exception as e:
        print(f"Error fetching current price for {ticker}: {e}")
        return 0.0
