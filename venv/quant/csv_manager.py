import os
import pandas as pd
import re

# 데이터 저장 경로
DATA_DIR = "data"
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio_data.csv")
ACCOUNT_VALUE_FILE = os.path.join(DATA_DIR, "account_value.csv")

# 컬럼 매핑 (한글 → 영어)
COLUMN_MAP = {
    "구분": "type", "구분.1": "type_1", "계좌번호": "account_number",
    "종목명": "ticker", "평가손익": "profit_loss", "손익률": "profit_rate",
    "잔고수량": "quantity", "매입단가": "purchase_price", "매입금액": "purchase_amount",
    "평가금액": "evaluation_amount", "평가비중": "evaluation_ratio"
}


def extract_date_from_filename(filename):
    """ 파일명에서 날짜(YYYY-MM-DD) 추출 """
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else None  # 날짜 형식이면 반환, 아니면 None


def get_latest_csv():
    """ 날짜 형식 CSV 파일 중 가장 최신 파일 반환 """
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and extract_date_from_filename(f)]
    return os.path.join(DATA_DIR, max(csv_files, key=extract_date_from_filename)) if csv_files else None


def get_all_csv_files():
    """ 날짜 형식 CSV 파일 목록 반환 (오래된 순서부터 정렬) """
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and extract_date_from_filename(f)]
    return sorted(csv_files, key=extract_date_from_filename)


def process_account_value():
    """ 모든 날짜 형식 CSV에서 날짜별 총 평가금액을 추출하여 account_value.csv 생성 """
    csv_files = get_all_csv_files()
    if not csv_files:
        print("❌ No valid CSV files found for account value processing.")
        return

    account_values = []
    for csv_file in csv_files:
        file_date = extract_date_from_filename(csv_file)
        df = pd.read_csv(os.path.join(DATA_DIR, csv_file), encoding="utf-8-sig", usecols=["평가금액"])
        total_value = df["평가금액"].astype(str).str.replace(",", "").astype(float).sum()
        account_values.append({"date": file_date, "total_value": total_value})

    pd.DataFrame(account_values).sort_values(by="date").to_csv(ACCOUNT_VALUE_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ Account Value CSV Updated with {len(account_values)} records.")


def process_portfolio_data():
    """ 가장 최신 날짜 형식 CSV에서 포트폴리오 데이터 추출하여 portfolio_data.csv 생성 """
    latest_csv = get_latest_csv()
    df = pd.read_csv(latest_csv, encoding="utf-8-sig")
    # ✅ 4번째 행이 중복 헤더일 경우 제거
    if len(df) > 3 and "구분" in df.iloc[3].values:
        df.drop(index=3, inplace=True)
        df.reset_index(drop=True, inplace=True)
    # ✅ 컬럼 변환 및 필터링
    df.columns = df.columns.str.strip()
    df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns}, inplace=True)
    portfolio_df = df[["type", "ticker", "evaluation_amount", "evaluation_ratio"]].copy()
    # ✅ 데이터 변환 및 NaN 처리
    portfolio_df["evaluation_amount"] = portfolio_df["evaluation_amount"].astype(str).str.replace(",", "").astype(
        float).fillna(0)
    portfolio_df.loc[:, "ticker"] = portfolio_df["ticker"].fillna(portfolio_df["type"])
    # ✅ 저장
    portfolio_df.to_csv(PORTFOLIO_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ Portfolio Data CSV Processed from {latest_csv}")

if __name__ == "__main__":
    process_account_value()
    process_portfolio_data()
