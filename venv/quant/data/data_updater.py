import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import os

def update_data(ticker, last_date, save_path="data/", market="global"):
    """
    기존 데이터에 실시간 데이터를 추가로 업데이트합니다.

    Args:
        ticker (str): 주식 또는 지수의 티커.
        last_date (str): 기존 데이터의 마지막 날짜 (예: '2023-12-31').
        save_path (str): 기존 데이터가 저장된 경로.
        market (str): 시장 구분 ('global' 또는 'kr').

    Returns:
        pd.DataFrame: 업데이트된 데이터프레임.
    """
    file_path = os.path.join(save_path, f"{ticker}_{market}.csv")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} does not exist. Please run `load_data` first.")

    # 기존 데이터 불러오기
    try:
        existing_data = pd.read_csv(file_path, index_col=0, parse_dates=True)
    except Exception as e:
        print(f"Error reading existing data for {ticker}: {e}")
        return pd.DataFrame()

    # 실시간 데이터 로드
    print(f"Updating data for {ticker} from {last_date} to today...")
    try:
        if market == "global":
            new_data = yf.download(ticker, start=last_date)
        elif market == "kr":
            new_data = fdr.DataReader(ticker, start=last_date)
        else:
            raise ValueError("Invalid market. Use 'global' or 'kr'.")
    except Exception as e:
        print(f"Error updating data for {ticker}: {e}")
        return existing_data

    # 기존 데이터와 병합
    updated_data = pd.concat([existing_data, new_data])
    updated_data = updated_data[~updated_data.index.duplicated(keep='last')]  # 중복 제거
    
    # 업데이트된 데이터 저장
    try:
        updated_data.to_csv(file_path)
        print(f"Data for {ticker} updated and saved to {file_path}")
    except Exception as e:
        print(f"Error saving updated data for {ticker}: {e}")
        return existing_data

    return updated_data
