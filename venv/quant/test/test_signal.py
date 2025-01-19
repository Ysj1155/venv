# tests/test_signals.py
from analysis.indicators import calculate_moving_average, calculate_rsi
from analysis.signal_generator import generate_moving_average_signals, generate_rsi_signals
import pandas as pd

def test_calculate_moving_average():
    """
    이동평균선 계산 테스트.
    """
    data = pd.DataFrame({"Close": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    ma = calculate_moving_average(data, window=3)
    assert len(ma) == len(data), "Moving average length mismatch."
    assert not ma.isnull().all(), "All moving average values are NaN."
    print("test_calculate_moving_average passed.")

def test_calculate_rsi():
    """
    RSI 계산 테스트.
    """
    data = pd.DataFrame({"Close": [1, 2, 3, 2, 1, 2, 3, 4, 3, 2]})
    rsi = calculate_rsi(data)
    assert len(rsi) == len(data), "RSI length mismatch."
    assert not rsi.isnull().all(), "All RSI values are NaN."
    print("test_calculate_rsi passed.")

def test_generate_signals():
    """
    매매 신호 생성 테스트.
    """
    data = pd.DataFrame({
        "Close": [1, 2, 3, 4, 3, 2, 3, 4, 5, 6]
    })
    data = generate_moving_average_signals(data, short_window=3, long_window=5)
    data = generate_rsi_signals(data, rsi_upper=70, rsi_lower=30)
    assert "Golden_Cross" in data.columns, "Golden_Cross signal missing."
    assert "RSI" in data.columns, "RSI column missing."
    print("test_generate_signals passed.")

if __name__ == "__main__":
    test_calculate_moving_average()
    test_calculate_rsi()
    test_generate_signals()

assert any(data['Golden_Cross']), "Golden Cross signal not detected."
assert any(data['Dead_Cross']), "Dead Cross signal not detected."
assert any(data['Golden_Cross']), "No Golden Cross detected."
