import pandas as pd
from utils import get_connection

def clean_int(val):
    return int(float(str(val).replace(",", "").replace("%", "")))

def clean_float(val):
    return float(str(val).replace(",", "").replace("%", ""))

def migrate_portfolio():
    df = pd.read_csv("data/portfolio_data.csv", encoding="utf-8-sig")
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM portfolio")
        for _, row in df.iterrows():
            cur.execute("""
                INSERT INTO portfolio (
                    account_number, ticker, quantity,
                    purchase_amount, evaluation_amount,
                    profit_loss, profit_rate, evaluation_ratio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row["account_number"],
                row["ticker"],
                clean_int(row["quantity"]),
                clean_int(row["purchase_amount"]),
                clean_int(row["evaluation_amount"]),
                clean_int(row["profit_loss"]),
                clean_float(row["profit_rate"]),
                clean_float(row["evaluation_ratio"]),
            ))
        conn.commit()
    conn.close()

def migrate_account_value():
    df = pd.read_csv("data/account_value.csv", encoding="utf-8-sig")
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM account_value")
        for _, row in df.iterrows():
            cur.execute("INSERT INTO account_value (date, total_value) VALUES (%s, %s)", (
                row["date"], clean_int(row["total_value"])
            ))
        conn.commit()
    conn.close()
