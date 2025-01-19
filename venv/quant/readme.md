# Trading Assistant 프로젝트

## **프로젝트 개요**
Trading Assistant는 주식 계좌 관리, 매매 신호 생성, 데이터 시각화 및 실시간 알림을 제공하는 통합 애플리케이션입니다. Flask 웹 애플리케이션과 PyQt 위젯을 활용해 사용자가 계좌 데이터를 입력하고 시각적으로 분석할 수 있도록 설계되었습니다.

---

## **기능 설명**

### 1. 데이터 관리 (`data/`)
- **`data_loader.py`**:
  - `yfinance` 및 `FinanceDataReader`를 사용하여 주식 데이터를 수집하고 로컬에 저장.
  - 글로벌 및 한국 시장 데이터를 모두 지원.
- **`data_updater.py`**:
  - 기존 데이터를 갱신하여 최신 상태로 유지.
  - 데이터 병합 및 중복 제거 기능 포함.

### 2. 기술적 분석 및 신호 생성 (`analysis/`)
- **`indicators.py`**:
  - 이동평균선, 볼린저 밴드, RSI, OBV 계산.
- **`signal_generator.py`**:
  - 골든 크로스, 데드 크로스, 급등/급락 신호 생성.
  - 추가적인 기술적 지표 확장 가능.

### 3. 알림 시스템 (`notifications/`)
- **`notifier.py`**:
  - Discord 웹훅을 통해 실시간 알림 전송.
  - 이미지 및 하이퍼링크를 포함한 알림 포맷 지원.
- **`test_noti.py`**:
  - 알림 시스템의 기능을 테스트.

### 4. 데이터 시각화 (`visualization/`)
- **`charts.py`**:
  - Plotly를 사용한 대화형 차트 생성.
  - 계좌 성장 그래프 및 기술적 지표 시각화.
- **`widget.py`**:
  - PyQt 기반의 데스크톱 위젯 구현.
  - 보유 종목 정보를 실시간으로 표시.

### 5. 웹 애플리케이션 (`app.py`)
- Flask를 사용한 웹 애플리케이션 구현.
- 주요 기능:
  - 계좌 데이터 입력 및 저장.
  - 그래프를 통해 계좌 성장 데이터 시각화.
  - 보유 종목 목록 및 실시간 수익률 표시.

### 6. 테스트 (`tests/`)
- **`test_data.py`**:
  - 데이터 수집 및 갱신 로직 검증.
- **`test_signal.py`**:
  - 매매 신호 생성 기능 테스트.
- **`test_noti.py`**:
  - 알림 시스템 테스트.

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

### 3. **Flask 앱 실행**
```bash
python app.py
```
- 브라우저에서 `http://127.0.0.1:5000/`로 접속.

---

## **디렉터리 구조**
```
quant/
├── app.py                  # Flask 애플리케이션 메인 파일
├── data/
│   ├── data_loader.py      # 데이터 수집
│   ├── data_updater.py     # 데이터 갱신
│   └── account_data.csv    # 계좌 데이터 저장
├── analysis/
│   ├── indicators.py       # 기술적 지표 계산
│   ├── signal_generator.py # 매매 신호 생성
├── notifications/
│   ├── notifier.py         # 알림 시스템 구현
│   ├── test_noti.py        # 알림 테스트
├── visualization/
│   ├── charts.py           # 데이터 시각화
│   ├── widget.py           # PyQt 위젯
├── tests/
│   ├── test_data.py        # 데이터 관리 테스트
│   ├── test_signal.py      # 신호 생성 테스트
├── templates/
│   └── index.html          # Flask HTML 템플릿
├── static/
│   ├── script.js           # 클라이언트 스크립트
├── config.py               # 환경 설정 파일
├── requirements.txt        # Python 의존성 파일
└── README.md               # 프로젝트 설명 파일
```

---

## **향후 개선 방향**
1. **알림 시스템 확장**:
   - 이메일 및 SMS 알림 추가.
   - 사용자 정의 조건 기반 알림.
2. **실시간 데이터 스트리밍**:
   - WebSocket을 활용하여 실시간 주식 데이터 반영.
3. **데이터 시각화 개선**:
   - 추가 지표(MACD, 스토캐스틱 등)를 차트에 추가.
   - 테이블과 그래프 간 상호작용 지원.
4. **사용자 인증 및 다중 계정 지원**:
   - 사용자별 데이터 분리 및 관리.
