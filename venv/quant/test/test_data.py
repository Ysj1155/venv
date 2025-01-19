# tests/test_data.py
from data.data_loader import load_data
from data.data_updater import update_data
import os

def test_load_data():
    """
    데이터 수집 테스트.
    """
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    save_path = "data/test/"
    data = load_data(ticker, start_date, end_date, save_path)

    # 테스트: 데이터프레임 확인
    assert not data.empty, "Data loading failed: DataFrame is empty."
    assert os.path.exists(f"{save_path}/{ticker}.csv"), "Data file was not saved."
    print("test_load_data passed.")

def test_update_data():
    """
    데이터 갱신 테스트.
    """
    ticker = "AAPL"
    last_date = "2023-12-01"
    save_path = "data/test/"
    data = update_data(ticker, last_date, save_path)

    # 테스트: 데이터프레임 확인
    assert not data.empty, "Data updating failed: DataFrame is empty."
    print("test_update_data passed.")

if __name__ == "__main__":
    test_load_data()
    test_update_data()
