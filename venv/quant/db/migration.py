import pandas as pd
from utils import get_connection


def _begin(conn):
    """mysql-connector / pymysql 둘 다 대응"""
    try:
        conn.start_transaction()
    except Exception:
        try:
            conn.begin()
        except Exception:
            # 일부 드라이버는 autocommit=False로만 트랜잭션이 잡힘
            pass


def clean_int(val, default=0) -> int:
    """'1,234', '12.3%', NaN, '' 등을 안전하게 int로."""
    if val is None or (isinstance(val, float) and pd.isna(val)) or (isinstance(val, str) and val.strip() == ""):
        return default
    s = str(val).replace(",", "").replace("%", "").strip()
    if s == "" or s.lower() == "nan":
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def clean_float(val, default=0.0) -> float:
    """'12.3%', NaN, '' 등을 안전하게 float로."""
    if val is None or (isinstance(val, float) and pd.isna(val)) or (isinstance(val, str) and val.strip() == ""):
        return default
    s = str(val).replace(",", "").replace("%", "").strip()
    if s == "" or s.lower() == "nan":
        return default
    try:
        return float(s)
    except Exception:
        return default


def migrate_portfolio(csv_path: str = "data/portfolio_data.csv"):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r.get("account_number"),
            r.get("ticker"),
            clean_int(r.get("quantity")),
            clean_int(r.get("purchase_amount")),
            clean_int(r.get("evaluation_amount")),
            clean_int(r.get("profit_loss")),
            clean_float(r.get("profit_rate")),
            clean_float(r.get("evaluation_ratio")),
        ))

    conn = get_connection()
    try:
        _begin(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM portfolio")
            cur.executemany("""
                INSERT INTO portfolio (
                    account_number, ticker, quantity,
                    purchase_amount, evaluation_amount,
                    profit_loss, profit_rate, evaluation_ratio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, rows)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def migrate_account_value(csv_path: str = "data/account_value.csv"):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r.get("date"),
            clean_int(r.get("total_value")),
        ))

    conn = get_connection()
    try:
        _begin(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM account_value")
            cur.executemany(
                "INSERT INTO account_value (date, total_value) VALUES (%s, %s)",
                rows
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()