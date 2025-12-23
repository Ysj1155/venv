from flask import Flask, render_template
from markupsafe import Markup
import markdown
import os

from db.migration import migrate_portfolio, migrate_account_value
from data.csv_manager import process_account_value, process_portfolio_data

from routes.portfolio import portfolio_bp
from routes.watchlist import watchlist_bp
from routes.market import market_bp
from routes.stocks import stocks_bp
from routes.health import health_bp
from routes.market_extra import market_extra_bp
from routes.valuation import valuation_bp

AUTO_REFRESH_CSV = os.getenv("AUTO_REFRESH_CSV", "false").lower() in ("1", "true", "yes", "y")


def bootstrap_refresh():
    """1) data/*.csv 원본 → 중간산출물 생성  2) DB 마이그레이션"""
    if not AUTO_REFRESH_CSV:
        print("ℹ️ AUTO_REFRESH_CSV=FALSE → CSV 갱신 스킵")
        return

    try:
        print("🔄 CSV 재생성 시작")
        process_account_value()
        process_portfolio_data()
        print("✅ CSV 재생성 완료")
    except Exception as e:
        print(f"❌ CSV 재생성 오류: {e}")

    try:
        print("🔄 DB 마이그레이션 시작")
        migrate_portfolio()
        migrate_account_value()
        print("✅ DB 마이그레이션 완료")
    except Exception as e:
        print(f"❌ DB 마이그레이션 오류: {e}")


app = Flask(__name__)

# 블루프린트 등록 (URL 유지)
app.register_blueprint(portfolio_bp)
app.register_blueprint(watchlist_bp)
app.register_blueprint(market_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(health_bp)
app.register_blueprint(market_extra_bp)
app.register_blueprint(valuation_bp)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/readme")
def show_readme():
    with open("readme.md", "r", encoding="utf-8") as f:
        content = f.read()
        html = markdown.markdown(content)
        return f"<div style='padding:40px;'>{Markup(html)}</div>"


@app.route("/favicon.ico")
def favicon():
    return "", 204


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Quant dashboard server")
    parser.add_argument("--refresh", action="store_true",
                        help="Regenerate CSVs and migrate DB BEFORE starting the server")
    args = parser.parse_args()

    if args.refresh:
        # debug=True 리로더 2회 실행 방지
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") is None:
            bootstrap_refresh()

    app.run(debug=True)