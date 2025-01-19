# Trading Assistant

## **프로젝트 개요**
Trading Assistant는 주식 계좌 관리와 매매 신호 분석을 돕기 위한 도구입니다.

이 프로그램은 다음과 같은 주요 기능을 제공합니다:
- **데이터 수집 및 갱신**: 주식 데이터를 자동으로 수집하고 최신 상태로 유지.
- **기술적 지표 계산**: 이동평균선, RSI, 볼린저 밴드 등.
- **매매 신호 생성**: 골든 크로스, 데드 크로스 등.
- **알림 시스템**: Discord를 통해 매매 신호 및 급등/급락 알림.
- **데이터 시각화**: 차트와 위젯을 통한 분석 결과 표시.

---

## **기능 설명**

### 1. 데이터 수집 및 갱신 (`data`)
- **`data_loader.py`**: 초기 주식 데이터 수집 및 로컬 저장.
- **`data_updater.py`**: 기존 데이터를 최신 데이터로 갱신.

### 2. 분석 및 매매 신호 생성 (`analysis`)
- **`indicators.py`**: 기술적 지표 계산.
  - 이동평균선(MA), 볼린저 밴드, RSI.
- **`signal_generator.py`**: 매매 신호 생성.
  - 골든 크로스, 데드 크로스, 급등/급락 신호 등.

### 3. 알림 시스템 (`notifications`)
- **`notifier.py`**: Discord를 통해 알림 전송.
  - 모바일 및 데스크톱에서 알림 확인 가능.

### 4. 데이터 시각화 (`visualization`)
- **`charts.py`**: 분석 데이터를 기반으로 차트 생성.
- **`widget.py`**: 데스크톱 위젯을 통해 실시간 데이터 표시.

### 5. 설정 관리 (`config.py`)
- Discord 웹훅 URL, 데이터 경로, 알림 조건 등 설정.

### 6. 테스트 (`tests`)
- 각 모듈의 기능 테스트:
  - `test_data.py`: 데이터 수집 및 갱신 테스트.
  - `test_signals.py`: 기술적 지표 및 신호 생성 테스트.
  - `test_notifier.py`: 알림 전송 테스트.

---

## **설치 및 실행 방법**

### 1. **환경 설정**
Python 가상 환경을 생성하고 활성화:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. **필요한 라이브러리 설치**
```bash
pip install -r requirements.txt
```

### 3. **Discord 웹훅 설정**
1. Discord 서버에서 웹훅 URL을 생성.
2. `config.py`에 웹훅 URL을 설정:
   ```python
   DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL"
   ```

### 4. **프로그램 실행**
```bash
python main.py
```

---

## **디렉터리 구조**
```
trading_assistant/
├── main.py                  # 메인 실행 파일
├── config.py                # 설정 파일 (API 키, 사용자 환경설정 등)
├── data/
│   ├── data_loader.py       # 데이터 수집 및 전처리
│   ├── data_updater.py      # 실시간 데이터 갱신
├── analysis/
│   ├── indicators.py        # 기술적 지표 계산 (이동 평균선, RSI 등)
│   ├── signal_generator.py  # 매수/매도 신호 생성
├── notifications/
│   ├── notifier.py          # 알림 기능 구현 (Discord 알림)
├── visualization/
│   ├── charts.py            # 데이터 시각화 (차트, 계좌 변동 그래프 등)
│   ├── widget.py            # 데스크톱 위젯 구현
├── tests/
│   ├── test_data.py         # 데이터 관련 테스트
│   ├── test_signals.py      # 신호 생성 테스트
│   ├── test_notifier.py     # 알림 기능 테스트
├── requirements.txt         # 프로젝트 의존성 목록
└── README.md                # 프로젝트 설명 파일
```

---

## **라이브러리 의존성**
- `pandas`: 데이터 처리.
- `numpy`: 수치 연산.
- `matplotlib`: 데이터 시각화.
- `plotly`: 대화형 차트 생성.
- `requests`: API 요청 및 웹훅 전송.
- `plyer`: 데스크톱 알림.
- `yfinance`: 주식 데이터 수집.

---

## **향후 개선 방향**
1. **알림 시스템 확장**:
   - 이메일 또는 SMS 알림 추가.
2. **실시간 데이터 처리**:
   - WebSocket을 활용한 실시간 주식 데이터 스트리밍.
3. **추가 기술적 지표 지원**:
   - MACD, 스토캐스틱 등 추가.
4. **UI 개선**:
   - PyQt를 활용한 데스크톱 GUI 개발.

