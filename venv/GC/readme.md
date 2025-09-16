# SSD Garbage Collection Simulator

## 프로젝트 개요
본 프로젝트는 **SSD(솔리드 스테이트 드라이브)의 Garbage Collection(GC) 알고리즘을 시뮬레이션하고 시각화**하는 것을 목표로 합니다.  
SSD는 NAND 플래시 메모리를 기반으로 하며, 덮어쓰기 불가(erase-before-write)라는 특성 때문에 **GC 과정**이 필수적입니다.  
그러나 GC는 SSD의 **쓰기 증폭(Write Amplification)**, **성능 저하**, **수명 단축**을 유발할 수 있습니다:contentReference[oaicite:0]{index=0}.  

본 연구에서는 다양한 GC 정책(예: Greedy, Cost-Benefit, BSGC 등)을 소프트웨어로 구현하여, **워크로드별 성능 차이를 정량적으로 분석**합니다.  
이를 통해 GC가 SSD 성능, 내구성, QoS에 미치는 영향을 파악하고, 시각화 및 비교를 통해 이해를 돕는 것이 핵심 목표입니다.

---

## 연구 목적
- **학술적 동기**  
  - SSD GC는 오버헤드가 크고, QoS 저하 및 지연(latency)을 유발.
  - 기존 연구는 효율적인 희생 블록 선택(Greedy, CB, CAT, BSGC 등) 기법을 제안했으나, 실제 워크로드 시뮬레이션 기반 비교가 부족.
- **실무적 동기**  
  - 데이터센터·실시간 시스템에서는 tail latency와 안정적인 성능 보장이 필요.
  - GC 정책 차이가 RocksDB 등 DBMS와 스토리지 계층의 성능에 직접적인 영향을 미침.

따라서 본 프로젝트는 **알고리즘별 GC 효과를 직접 구현·시뮬레이션·분석**하는 것을 통해 학술적/실무적 통찰을 제공하려 합니다.

---

## 현재까지 진행 상황
1. **개발 환경 세팅**
   - `venv` 가상환경 생성 및 `GC` 디렉토리 구축
   - Python 기반 시뮬레이터 코드 초기 작성

2. **GC 알고리즘 구현**
   - Greedy 정책 구현 및 실행 성공
   - 실행 명령어 예시:
     ```bash
     python run_sim.py --gc_policy greedy --ops 5000 --update_ratio 0.8
     ```

3. **실험 결과**  
=== Simulation Result ===
Host writes (pages):   5,000  
Device writes (pages): 5,639  
WAF (device/host):     1.128  
GC count:              243  
Avg erase per block:   0.95 (min=0, max=2, Δ=2)  
Free pages remaining:  13849 / 16384    
- Host write 대비 Device write가 많아 쓰기 증폭 발생(WAF > 1)
- Garbage Collection이 243회 수행됨    
- 정상적으로 GC 동작 및 성능 지표 산출 확인    

---

## 📅 앞으로의 계획
- [ ] Cost-Benefit, CAT, BSGC 등 다른 GC 알고리즘 구현
- [ ] GC 정책별 WAF, GC 횟수, 지연(latency) 비교
- [ ] RocksDB와 연계된 DB workload 적용 실험
- [ ] 시각화(그래프) 도구를 통해 성능 차이 분석
- [ ] 최종 보고서 및 발표 자료 제작

---

## 📖 참고 문헌
- 김한얼, *머신러닝 알고리즘을 통한 SSD 가비지 컬렉션 감지 및 관리 기법*, 홍익대, 2014:contentReference[oaicite:6]{index=6}  
- 오승진, *RocksDB SSTable 크기가 성능에 미치는 영향 분석*, 성균관대, 2022:contentReference[oaicite:7]{index=7}  
- 김성호 외, *SSD 기반 저장장치 시스템에서 마모도 균형과 내구성 향상을 위한 가비지 컬렉션 기법*, 한국컴퓨터정보학회논문지, 2017:contentReference[oaicite:8]{index=8}  
- 박상혁, *Analysis of the K2 Scheduler for a Real-Time System with a SSD*, 성균관대, 2021:contentReference[oaicite:9]{index=9}

---
