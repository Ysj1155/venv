# analysis/indicators.py
import pandas as pd

def calculate_moving_average(data, window):
    """
    이동평균선 계산
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close').
        window (int): 이동평균 계산 기간.
    Returns:
        pd.Series: 이동평균 값.
    """
    return data['Close'].rolling(window=window).mean()

def calculate_bollinger_bands(data, window=20, num_std=2):
    """
    볼린저 밴드 계산
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close').
        window (int): 이동평균 계산 기간.
        num_std (int): 표준편차 계수.
    Returns:
        pd.DataFrame: 상단, 하단 밴드 포함 데이터프레임.
    """
    ma = data['Close'].rolling(window=window).mean()
    std = data['Close'].rolling(window=window).std()
    data['Upper_Band'] = ma + (num_std * std)
    data['Lower_Band'] = ma - (num_std * std)
    return data

def calculate_rsi(data, window=14):
    """
    RSI 계산
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close').
        window (int): RSI 계산 기간.
    Returns:
        pd.Series: RSI 값.
    """
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_obv(data):
    """
    OBV(On-Balance Volume) 계산
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close', 'Volume').
    Returns:
        pd.Series: OBV 값.
    """
    obv = (data['Volume'] * ((data['Close'] > data['Close'].shift()).astype(int) -
                             (data['Close'] < data['Close'].shift()).astype(int))).cumsum()
    return obv

if data.empty:
    raise ValueError("Input data is empty.")
 