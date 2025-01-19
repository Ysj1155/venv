# analysis/signal_generator.py
from analysis.indicators import calculate_moving_average, calculate_rsi

def generate_moving_average_signals(data, short_window=5, long_window=20):
    """
    이동평균선을 기반으로 골든 크로스와 데드 크로스 신호 생성
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close').
        short_window (int): 단기 이동평균선 기간.
        long_window (int): 장기 이동평균선 기간.
    Returns:
        pd.DataFrame: 매수/매도 신호가 추가된 데이터프레임.
    """
    data['Signal_Date'] = data.index.where(data['Golden_Cross'] | data['Dead_Cross'])
    data['Short_MA'] = calculate_moving_average(data, short_window)
    data['Long_MA'] = calculate_moving_average(data, long_window)
    data['Golden_Cross'] = (data['Short_MA'] > data['Long_MA']) & (data['Short_MA'].shift(1) <= data['Long_MA'].shift(1))
    data['Dead_Cross'] = (data['Short_MA'] < data['Long_MA']) & (data['Short_MA'].shift(1) >= data['Long_MA'].shift(1))
    return data

def generate_rsi_signals(data, rsi_upper=70, rsi_lower=30):
    """
    RSI를 기반으로 과매수/과매도 신호 생성
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close').
        rsi_upper (int): RSI 과매수 기준.
        rsi_lower (int): RSI 과매도 기준.
    Returns:
        pd.DataFrame: 매수/매도 신호가 추가된 데이터프레임.
    """
    data['RSI'] = calculate_rsi(data)
    data['Overbought'] = data['RSI'] > rsi_upper
    data['Oversold'] = data['RSI'] < rsi_lower
    return data

def generate_rapid_change_signals(data, threshold=5):
    """
    급등/급락 감지
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Close').
        threshold (float): 급등/급락 기준 변화율(백분율).
    Returns:
        pd.DataFrame: 급등/급락 신호가 추가된 데이터프레임.
    """
    data['Change'] = data['Close'].pct_change() * 100
    data['Rapid_Surge'] = data['Change'] > threshold
    data['Rapid_Drop'] = data['Change'] < -threshold
    return data
