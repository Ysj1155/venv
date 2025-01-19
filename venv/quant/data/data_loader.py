import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import os

def load_data(ticker, start_date, end_date, save_path="data/", market="global"):
    """
    특정 티커의 데이터를 로드하고 로컬에 저장합니다.

    Args:
        ticker (str): 주식 또는 지수의 티커 (예: 'AAPL', '^GSPC' 또는 '005930' for Samsung Electronics).
        start_date (str): 데이터 시작 날짜 (예: '2023-01-01').
        end_date (str): 데이터 종료 날짜 (예: '2023-12-31').
        save_path (str): 저장 경로 (기본값: 'data/').
        market (str): 시장 구분 ('global' 또는 'kr').

    Returns:
        pd.DataFrame: 로드된 데이터프레임.
    """
    print(f"Loading data for {ticker} from {start_date} to {end_date}...")

    try:
        # Global market 데이터 로드 (yfinance)
        if market == "global":
            data = yf.download(ticker, start=start_date, end=end_date)
        # Korean market 데이터 로드 (FinanceDataReader)
        elif market == "kr":
            data = fdr.DataReader(ticker, start_date, end_date)
        else:
            raise ValueError("Invalid market. Use 'global' or 'kr'.")
    except Exception as e:
        print(f"Failed to load data for {ticker}: {e}")
        return pd.DataFrame()

    # 저장 경로 생성
    os.makedirs(save_path, exist_ok=True)
    file_path = os.path.join(save_path, f"{ticker}_{market}.csv")

    # CSV 저장
    data.to_csv(file_path)
    print(f"Data saved to {file_path}")
    return data

def load_multiple_tickers(tickers, start_date, end_date, save_path="data/", market="global"):
    """
    여러 티커의 데이터를 로드하고 저장합니다.

    Args:
        tickers (list): 주식 또는 지수 티커 목록.
        start_date (str): 데이터 시작 날짜.
        end_date (str): 데이터 종료 날짜.
        save_path (str): 저장 경로.
        market (str): 시장 구분 ('global' 또는 'kr').

    Returns:
        dict: 티커별 데이터프레임 딕셔너리.
    """
    data_frames = {}
    for ticker in tickers:
        try:
            data_frames[ticker] = load_data(ticker, start_date, end_date, save_path, market)
        except Exception as e:
            print(f"Error loading data for {ticker}: {e}")
    return data_frames
