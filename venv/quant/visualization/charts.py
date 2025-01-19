# visualization/charts.py
import plotly.graph_objects as go
import pandas as pd

def plot_candlestick_with_indicators(data, title="Candlestick Chart with Indicators"):
    """
    캔들스틱 차트에 이동평균선과 볼린저 밴드를 추가하여 시각화.
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Open', 'High', 'Low', 'Close', 'Short_MA', 'Long_MA', 'Upper_Band', 'Lower_Band').
        title (str): 차트 제목.
    """
    fig = go.Figure()

    # 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="Candlestick"
    ))

    # 이동평균선
    fig.add_trace(go.Scatter(x=data.index, y=data['Short_MA'], mode='lines', name='Short MA'))
    fig.add_trace(go.Scatter(x=data.index, y=data['Long_MA'], mode='lines', name='Long MA'))

    # 볼린저 밴드
    fig.add_trace(go.Scatter(x=data.index, y=data['Upper_Band'], mode='lines', name='Upper Band'))
    fig.add_trace(go.Scatter(x=data.index, y=data['Lower_Band'], mode='lines', name='Lower Band', fill='tonexty'))

    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Price")
    fig.update_layout(hovermode="x")
    fig.show()

def plot_portfolio_returns(data, title="Portfolio Returns"):
    """
    계좌 잔고 변화 및 누적 수익률 시각화.
    Args:
        data (pd.DataFrame): 데이터프레임 (필수 열: 'Date', 'Cumulative Returns').
        title (str): 차트 제목.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Cumulative Returns'], mode='lines', name='Cumulative Returns'))
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Cumulative Returns")
    fig.show()

if data.empty or not all(col in data.columns for col in ['Open', 'High', 'Low', 'Close']):
    raise ValueError("Input data is invalid or missing required columns.")

