import os
import pandas as pd
import re

# 데이터 저장 경로
DATA_DIR = "data"
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio_data.csv")
ACCOUNT_VALUE_FILE = os.path.join(DATA_DIR, "account_value.csv")

# 컬럼 매핑 (한글 → 영어)
COLUMN_MAP = {
    "구분": "type",
    "구분.1": "type_1",
    "계좌번호": "account_number",
    "종목명": "ticker",
    "평가손익": "profit_loss",
    "손익률": "profit_rate",
    "잔고수량": "quantity",
    "매입단가": "purchase_price",
    "매입금액": "purchase_amount",
    "평가금액": "evaluation_amount",
    "평가비중": "evaluation_ratio",
}

def extract_date_from_filename(filename):
    """ 파일명에서 날짜(YYYY-MM-DD 형식)를 추출 """
    match = re.search(r"(\d{2}-\d{2})", filename)  # "02-06" 같은 패턴 찾기
    if match:
        return f"2025-{match.group(1)}"
    return None

def get_all_csv_files():
    """ 데이터 폴더에서 모든 CSV 파일 가져오기 """
    return [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]


def process_account_value():
    """모든 CSV 파일에서 날짜별 총 평가금액을 추출하여 account_value.csv 생성"""
    # ✅ 모든 CSV 파일 가져오기
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    if not csv_files:
        print("❌ No CSV file found for account value.")
        return
    account_values = []
    # ✅ 모든 파일 순회하면서 날짜별 평가금액 계산
    for csv_file in csv_files:
        file_date = extract_date_from_filename(csv_file)
        if not file_date:
            continue  # 날짜 추출 실패 시 스킵
        file_path = os.path.join(DATA_DIR, csv_file)
        # ✅ CSV 파일 읽고 필요한 컬럼만 처리
        df = pd.read_csv(file_path, encoding="utf-8-sig", usecols=["평가금액"])
        # ✅ 쉼표 제거 후 평가금액 변환 및 합산
        total_value = df["평가금액"].astype(str).str.replace(",", "").astype(float).sum()
        # ✅ 날짜별 총 평가금액 저장
        account_values.append({"date": file_date, "total_value": total_value})

    # ✅ DataFrame 생성 후 CSV 저장 (날짜순 정렬)
    account_value_df = pd.DataFrame(account_values)
    account_value_df.sort_values(by="date", inplace=True)
    account_value_df.to_csv(ACCOUNT_VALUE_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ Account Value CSV Updated with {len(account_values)} records.")


def process_portfolio_data():
    """ 가장 최신 CSV 파일을 사용하여 portfolio_data.csv 생성 (4번째 행 제거 후 처리) """
    # ✅ 최신 CSV 파일 찾기 (account_value.csv 제외)
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and "account_value" not in f]
    if not csv_files:
        print("❌ No CSV file found. Skipping portfolio data processing.")
        return
    latest_csv = os.path.join(DATA_DIR, max(csv_files))
    # ✅ 최신 CSV 파일 읽기 (4번째 행 제거)
    try:
        latest_df = pd.read_csv(latest_csv, encoding="utf-8-sig")
        latest_df.drop(index=3, inplace=True)  # 4번째 행 제거 (index=3)
        latest_df.reset_index(drop=True, inplace=True)  # 인덱스 리셋
    except Exception as e:
        print(f"❌ Error reading CSV file {latest_csv}: {e}")
        return
    # ✅ 컬럼명을 강제로 정리 (공백 제거)
    latest_df.columns = [col.strip() for col in latest_df.columns]
    # ✅ 컬럼 변환 실행 (존재하는 컬럼만 변경)
    latest_df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in latest_df.columns}, inplace=True)
    # ✅ 변환 후 컬럼 확인
    print(f"✅ After renaming columns: {latest_df.columns.tolist()}")
    # ✅ 'type' 컬럼이 없을 경우 오류 방지
    if "type" not in latest_df.columns:
        print(f"❌ 'type' 컬럼이 없습니다. 확인이 필요합니다. 파일: {latest_csv}")
        return
    # ✅ 필요한 컬럼만 선택 (type 포함) + 명시적 복사
    required_columns = ["type", "ticker", "evaluation_amount", "evaluation_ratio"]
    portfolio_df = latest_df[[col for col in required_columns if col in latest_df.columns]].copy()
    # ✅ `evaluation_amount` 숫자로 변환 (쉼표 제거) + .loc 사용
    if "evaluation_amount" in portfolio_df.columns:
        portfolio_df.loc[:, "evaluation_amount"] = (
            portfolio_df["evaluation_amount"].astype(str).str.replace(",", "").astype(float)
        )
    # ✅ `ticker` 값이 NaN이면 `type` 값을 대신 사용 + .loc 사용
    if "ticker" in portfolio_df.columns:
        portfolio_df.loc[:, "ticker"] = portfolio_df["ticker"].fillna(portfolio_df["type"])
    # ✅ `portfolio_data.csv` 저장 (type 포함)
    portfolio_df.to_csv(PORTFOLIO_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ Portfolio Data CSV Processed from {latest_csv} (4th row removed)")

# 실행 예시
if __name__ == "__main__":
    process_account_value()  # ✅ 계좌 잔고 데이터 생성
    process_portfolio_data()  # ✅ 포트폴리오 데이터 생성
