# visualization/widget.py
import sys
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer

def start_timer(self):
    timer = QTimer(self)
    timer.timeout.connect(self.update_data)
    timer.start(5000)  # 5초마다 갱신


class StockWidget(QWidget):
    def __init__(self, stocks):
        super().__init__()
        self.initUI(stocks)

    def initUI(self, stocks):
        layout = QVBoxLayout()

        # 위젯 타이틀
        title = QLabel("Stock Information")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 종목 정보 표시
        for stock, info in stocks.items():
            label = QLabel(f"{stock}: {info['price']} ({info['change']}%)")
            label.setStyleSheet("font-size: 14px;")
            layout.addWidget(label)

        # 레이아웃 설정
        self.setLayout(layout)
        self.setWindowTitle("Stock Widget")
        self.resize(300, 200)

# 테스트 실행
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 샘플 데이터
    stocks = {
        "AAPL": {"price": 150.0, "change": "+1.5"},
        "GOOGL": {"price": 2800.0, "change": "-0.8"},
        "MSFT": {"price": 310.0, "change": "+2.1"}
    }

    widget = StockWidget(stocks)
    widget.show()
    sys.exit(app.exec_())
