# Trading Assistant

이 프로젝트는 개인의 주식 포트폴리오를 관리하고 시각화하는 Flask 기반의 웹 애플리케이션입니다.  
**MySQL 기반 백엔드**, **KIS 및 Finnhub API 연동**, **Plotly 시각화**를 통해 실시간 정보와 보유 자산을 종합적으로 분석할 수 있습니다.

---

## ✅ 주요 기능

### 📊 대시보드

- **포트폴리오 시각화**  
  MySQL에 저장된 데이터를 기반으로, 보유 종목의 수익률/평가금액/비중을 테이블과 파이 차트로 표시

- **계좌 잔고 추적**  
  `account_value` 테이블에서 날짜별 평가금액을 불러와 꺾은선 그래프와 수익률을 동시에 표시

- **섹터 분배 시각화**  
  S&P500 기준 섹터별 트리맵 + 내 보유 자산의 섹터별 비중을 비교 분석

- **환율 차트 시각화**  
  `USD/KRW` 환율 데이터를 선형 그래프로 표시 (FinanceDataReader 이용)

---

### ⭐ 관심 목록 (Watchlist)

- 종목 추가/삭제 가능 (프론트엔드에서 실시간 갱신)
- 종목 클릭 시:
  - **Finnhub API**로 실시간 시세, PER, 시총, 배당률 등 표시
  - **KIS API**로 일봉 캔들차트 + 거래량 표시
- DB 기반으로 전환되어 `watchlist.json` 파일 없이 완전 자동화됨
## 추가 예정 기능

- **관심 종목 분석 기능**: 관심 종목 리스트에서 각 종목의 5일, 10일, 20일 이동 평균선과 거래량을 시각화할 예정입니다. 관심 목록은 티커를 입력하면 API를 통해 관련 종목 정보를 업데이트하여 나열합니다.  
  추가로 다음과 같은 확장 기능도 계획:
  - 각 종목의 RSI, MACD, 볼린저 밴드 등 다양한 기술적 지표를 함께 시각화  
  - 관심 등록 이후 수익률 히스토리 추적 (관심 등록일 기준)  
  - S&P 500, QQQ 등의 주요 지수 대비 상대 강도 분석 (Relative Performance)  
  - 종목별 알림 조건 커스터마이징 (예: RSI < 30일일 때만 알림, 목표가 도달 시 알림 등)  
  - 기본 재무지표(PER, ROE 등)와 간단 요약 정보 제공  
  - 동일 섹터 및 산업군 내 유사 종목 자동 추천 기능  
  - 실시간 뉴스 헤드라인 또는 공시 정보 연동
- **골든크로스/데드크로스 알림**: 위의 이동 평균선을 기반으로 골든크로스 및 데드크로스 발생 시 디스코드를 통해 실시간 알림을 제공하는 기능을 추가할 예정입니다.
- **핸드폰 연동 시스템**: unity나 다른 방법을 사용해서 핸드폰으로 같은 화면을 볼 수 있는 방안 모색
## 주요 기능

- **포트폴리오 시각화**: 원형 다이어그램을 통해 보유 자산의 구성과 비율을 시각적으로 확인할 수 있습니다.
- **계좌 잔고 추적**: 날짜별 계좌의 총 평가금액 변화를 꺾은선 그래프로 시각화하여, 자산의 증가 및 감소 추이를 확인할 수 있습니다.
- **환율 정보 시각화**: USD/KRW 환율 변동을 선형 그래프로 표시하여 추세를 분석할 수 있습니다.
- **섹터 분배 시각화**: 보유 포트폴리오의 섹터별 비중을 트리맵 형태로 시각화하여, 시장과의 비교 분석이 가능합니다.
- **관심목록 관리**: 관심 있는 주식 종목을 리스트에 추가하고 관리할 수 있으며, 추후 알림 기능을 추가할 예정입니다.

## 🔧 설치 및 실행

```bash
git clone https://github.com/Ysj1155/venv.git
cd venv

# 가상환경 설정 (선택)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# .env 파일 생성
cp .env.example .env  # 또는 직접 appkey/secret 입력

# Flask 서버 실행
python app.py

## 파일 구조

```
quant/
├── app.py                  # Flask 서버 진입점 (라우팅 및 API 엔드포인트)
├── main.py                 # 관심 종목 수집 실행 스크립트
├── config.py               # 환경변수 로드 및 API 키/DB 설정
├── db/
│   └── migration.py        # CSV 데이터를 DB(portfolio/account_value)로 마이그레이션
├── api/
│   ├── finnhub_api.py      # Finnhub API 연동 (시세, 프로필, 지표, ETF holdings 등)
│   └── kis_api.py          # KIS API 연동 (일봉 캔들 데이터 조회 등)
├── utils.py                # DB 연결(get_connection), KIS OHLC 변환 유틸
├── templates/index.html    # 대시보드 프론트엔드 뷰
├── static/
│   ├── styles.css          # CSS 스타일 시트
│   └── script.js           # JS 로직 (차트 렌더링, 탭 전환, 관심목록 관리)
├── data/                   # 초기 데이터 CSV 저장 위치
├── requirements.txt        # 의존성 패키지 리스트
└── readme.md               # 프로젝트 문서
```

## API 엔드포인트

- /get_portfolio_data:        보유 종목 데이터 조회
- /get_pie_chart_data:        자산 비중 파이차트 데이터
- /get_account_value_data:    총 자산 추이 및 수익률
- /get_watchlist:             관심 종목 리스트 불러오기
- /add_watchlist:             관심 종목 추가
- /remove_watchlist:          관심 종목 삭제
- /get_stock_detail_finnhub:  종목 기본 정보 (시가총액, PER 등)
- /get_stock_chart_kis:       KIS 일봉 차트 데이터
- /get_exchange_rate_data:    USD/KRW 환율 데이터
- /get_treemap_data	S&P500:   섹터별 변동률
- /get_portfolio_sector_data: 내 자산의 섹터 분포

## 업데이트 내역
### ✅ [2025-07-22] MySQL 기반 전체 리팩터링 및 API 전환 완료
- 기존 CSV/JSON 파일 기반 구조에서 MySQL DB 기반으로 전환
- 주요 데이터(`portfolio`, `account_value`, `watchlist`)를 DB에 마이그레이션
- Flask API 리팩터링 완료:
  - `/get_portfolio_data`: 포트폴리오 DB 조회
  - `/get_account_value_data`: 평가금액 및 수익률 DB 조회
  - `/get_pie_chart_data`: 자산 비중 계산
  - `/get_watchlist`: 관심 종목 목록 DB 조회
  - `/add_watchlist`, `/remove_watchlist`: 관심 종목 DB 추가/삭제 처리
  - `/get_portfolio_sector_data`: 포트폴리오 섹터 분포 계산 (FDR + DB 연동)
- `db.py` 개선: `get_connection()` 함수 방식으로 안전한 커넥션 분리 구조 적용
- 모든 API에서 커서 및 커넥션을 지역화(`with conn.cursor(...)`)하여 안정성 확보
- `int64` 직렬화 오류 수정 (`int()` 처리)
- `watchlist.json` 파일 사용 중단 → MySQL `watchlist` 테이블로 완전 전환
- 관련 JSON 파일 및 파일 기반 함수 제거
### ✅ [2025-09-05] 프론트/백엔드 통합 개선 및 섹터 분석 업그레이드
- **포트폴리오 섹터 분석 업그레이드**
  - `/get_portfolio_sector_data`: ETF 보유 종목까지 look-through → GICS 섹터 기준으로 분해
  - 개별주식 + ETF를 합산한 실제 섹터 노출도를 트리맵으로 시각화
- **프론트엔드 레이아웃 개선**
  - `index.html`: 보조 자료 탭을 Bootstrap grid/card 구조로 개편 → S&P500 섹터 vs 내 포트폴리오 섹터 비교 가능
  - 환율 그래프를 별도 행에 배치
  - 메인 계좌 탭의 차트들도 카드 스타일(`.chart-card`) 적용 → UI 일관성 확보
- **CSS (`styles.css`)**
  - `.chart-card`, `.chart-title`, `.chart-box` 스타일 추가
  - 반응형 지원: 화면 폭이 좁을 때 Treemap 세로 정렬
  - 고정 높이(`height: 480px`) 적용으로 Plotly 레이아웃 안정화
- **JavaScript (`script.js`)**
  - 탭 전환 시 Treemap/환율 차트 크기 오류 수정 → `forceRelayout` 적용
  - 보조자료 탭: 처음 열릴 때만 데이터 로드, 이후에는 `resize`로만 갱신
- **백엔드 구조 정리**
  - `db.py` 파일 제거 → DB 연결(`get_connection`) 기능을 `utils.py`로 통합
  - `with conn.cursor(...)` 패턴 일괄 적용으로 안정성 확보
- **README**
  - API 엔드포인트 목록을 실제 구현 기준으로 정정
    - `/get_treemap_data` → "S&P500 섹터별 변동률"
    - `/get_portfolio_sector_data` → ETF look-through 기반 최신 로직 반영
  - 프로젝트 폴더 구조를 최신 코드 기준으로 업데이트
##

