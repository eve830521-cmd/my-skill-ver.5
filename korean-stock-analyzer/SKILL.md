---
name: korean-stock-analyzer
description: 한국 상장기업 DART 공시 및 글로벌 산업 딥리서치 기반 3-Phase 심층 가치평가 · 원샷 오케스트레이터(ksa_orchestrator.py) · 2-Tier 스마트 무손실 원문 발췌 · SOTP · S-Curve 10% 변곡점 · 3축 구조적 병목(Capa·기술·특허) · 병목해소리드타임 · K-주주환원스코어카드 · 레짐체크 · 사이클함정차단 · 주가=(수급+실적)*기대감 과거역추적 · 2-Tier 모델 커스텀 마스터 스킬 (v5.0)
---

# 🏛️ Korean Stock Analyzer 마스터 워크플로우 & 템플릿 규격서 (`SKILL.md` v5.0)

이 스킬은 한국 상장기업의 본원적 가치와 실전 매매 타점을 도출하기 위한 **단일 표준 규격서(v5.0)**입니다.
모든 분석은 **『1순위: 보고서 퀄리티 및 수리·회계·논리적 무결성 100% 사수 / 2순위: 원샷 오케스트레이터(`ksa_orchestrator.py`) 기반 토큰·쿼터 소모량 90% 절감(65회 도구 호출 ➔ 4~6회 압축)』** 대원칙을 따릅니다.

---

## ⚡ 제0원칙: v5.0 원샷 오케스트레이터(`ksa_orchestrator.py`) & 4~6턴 완결 파이프라인 규율

과거 65회의 파편화된 도구 호출(`read_file` 30회, 개별 파이썬 실행 24회)로 주간 한도 13%가 소모되던 문제를 원천 해결하기 위해, 에이전트는 반드시 아래 **4단계 원샷 실행 프로토콜**을 준수해야 합니다:

### 1. [Step 1 — 원샷 준비 명령 (`run_command` 단 1회)]
- `backtest_valuation.py`, `calc_reverse_dcf.py`, `parse_pdf.py`를 개별적으로 여러 번 실행하지 마십시오.
- `korean-dart` MCP(`search_disclosures`)로 최근 공시를 스캔한 직후, 아래 **`ksa_orchestrator.py prep` 명령 단 1회**로 ① 4대 폴더 초기화, ② 기존 SSOT 파라미터 자동 계승, ③ 10년 백테스트 & SOTP/병목/K-주주환원 연산, ④ 역DCF 3단 요구성장률 연산, ⑤ 2-Tier 스마트 무손실 PDF 원문 발췌(`verbatim_extracts.md`, 노이즈 제거 및 최대 18쪽 캡), ⑥ **단일 통합 브리핑(`ai_prep_digest.md`) 생성**을 한 번에 완료합니다:
  ```powershell
  python e:\antigravity-work\my-skill\korean-stock-analyzer\ksa_orchestrator.py prep --corp-name [기업명] [--code 종목코드] [신규/변경 파라미터만 추가]
  ```
  - **주요 옵션 (변경 시에만 입력, 미입력 시 기존 `valuation_metrics.json` 저장값 자동 계승)**:
    `--sector-type [A/B/C/D] --distb-shares [유통주식수] --total-shares [총주식수] --fcf [보고FCF억] --norm-fcf [오너정규화FCF억] --non-op-assets [비영업자산억] --net-debt [순차입금억] --rerating-date [YYYY-MM-DD] --dart-exposure [신기술매출비중%] --forward-eps [추정EPS] --forward-eps-g [EPS성장률%] --expected-dps [배당금] --penetration-pct [1차침투율%] --second-penetration-pct [2차침투율%] --bottleneck-grade [S/A/B/C] --bottleneck-months [리드타임개월] --capa-util-pct [가동률%] --shortage-easing --slope-decel --policy-headwind --clear-sell-signals --payout-ratio [배당성향%] --buyback-cliff --related-party-eok [내부거래억] --governance-discount [할인율%] --primary-keywords "핵심어1,핵심어2" --keywords "테마어1,테마어2"`

### 2. [Step 2 — 단일 통합 브리핑 로드 (`read_file` 단 1회)]
- `auto_tables.md`, `valuation_metrics.json`, `thesis_log.md`, `company_timeline.md`, `verbatim_extracts.md`를 각각 따로 `read_file` 하지 마십시오.
- 오직 **`Stock_Research/[기업명]/2_Translated_DB/ai_prep_digest.md` 파일 단 1개만 `read_file`로 읽으십시오.**
- 이 파일 안에 트랙 판정(`Track A` vs `Track B`), 코드 확정 마크다운 표 6종(`코드 자동 생성 1, 1-B, 1-C, 2, 2-B, 3`), 기존 6열 가설 및 타임라인, 그리고 2-Tier 필터링된 무손실 PDF 원문 발췌본이 모두 통합되어 있습니다.

### 3. [Step 3 — Track A(전면 작성) vs Track B(격주 핀셋 델타) 분기 실행]
- **🏛️ Track A (`신규 기업 최초 분석` / `분기·반기·사업보고서 신규 발표` / `빅 이벤트` / `구버전 클린 리빌드`)**:
  - `ai_prep_digest.md`의 `[코드 자동 생성 1, 1-B, 1-C, 2, 2-B, 3]` 표를 **단 1원도 AI가 임의로 수정하지 않고 그대로 삽입**하여 `Phase1_Report.md`, `Phase2_Story.md`, `thesis_log.md`, `Phase3_DCF.md`를 각각 독립된 `write_file` 호출로 무생략 작성합니다.
- **⚡ Track B (`격주 Global/Weekly Trend 점검` / `수시 공시·주가 반영 업데이트` — 이미 v4.3/v5.0 게이트가 완비된 기업)**:
  - **🚫 절대 금지**: 2주 만에 바뀌지 않는 `Phase1_Report.md`나 `Phase3_DCF.md` 전체를 다시 쓰거나(`write_file`), 단순 주가·목표가·매수가 숫자를 고치기 위해 `Phase1`·`Phase3`를 읽고 수동 편집하지 마십시오!
  - **✅ AI 전담 작업 (도구 호출 2~3회)**:
    1) `ai_prep_digest.md`의 신규 PDF 원문 발췌본과 최신 공시를 바탕으로 **`Weekly_Trend/company_timeline.md`**와 **`Weekly_Trend/thesis_log.md`(6열 포퍼식 가설 표)**를 `edit_file`로 핀셋 업데이트합니다.
    2) 핵심 서사나 리드타임 가정이 추가된 경우에만 `Phase2_Story.md`(또는 `Phase3_DCF.md` 시나리오 서술 칼럼)의 해당 문단을 `edit_file`로 보강합니다.
    3) `Phase1_Report.md`와 `Phase3_DCF.md`의 모든 주가·시총·멀티플·역DCF·목표가·3분할 매수가·안전핀·HTML 계산기 태그는 **Step 4의 `build --patch-ssot` 명령이 파이썬 코드로 100% 자동 치환**합니다!

### 4. [Step 4 — 원샷 빌드 & SSOT 자동 패치 & 무결성 검증 (`run_command` 단 1회)]
- 작성 또는 핀셋 수정이 끝나면 `generate_html.py`와 `validate_report.py`를 따로 호출하지 말고 아래 **통합 빌드 명령 단 1줄**을 실행하여 ① `Phase1/Phase3` 내 SSOT 테이블·주가·SOP·HTML 태그 자동 패치, ② `Phase 1~3` HTML 3종 일괄 생성, ③ `validate_report.py` 무결성 검증(`[PASS]`)을 한 번에 완료합니다:
  ```powershell
  python e:\antigravity-work\my-skill\korean-stock-analyzer\ksa_orchestrator.py build --corp-name [기업명] --patch-ssot
  ```

---

## 🤖 2-Tier 모델 역할 분담 및 후속 모델 커스텀 체계 (`model_config.json`)

Gemini AI Pro 환경에서 **1순위(보고서 퀄리티 극대화)**와 **2순위(토큰 효율성 극대화)**를 달성하기 위해 모델을 2개 티어로 운영하며, 구글이 후속 모델(예: `Argon Flash`, `Gemini 5.0` 등)을 발표할 경우 `python ksa_orchestrator.py set-models --tier1 "[신규1순위모델]" --tier2 "[신규2순위모델]"` 명령으로 즉시 커스텀합니다:

| 구분 | 현재 기본 모델 (`model_config.json`) | 핵심 전담 작업 (Best Fit Scenarios) | 원샷 파이프라인 연동 시 예상 주간 쿼터 소모 |
| :--- | :--- | :--- | :---: |
| **👑 1순위 모델 (`Tier-1`)**<br>*최상위 심층 추론 모델* | **`Gemini 4.0 Argon (Medium)`**<br>*(향후 4.5/5.0 Pro·Argon 후속작)* | • **신규 기업 최초 Phase 1~3 심층 분석 (`Track A`)**<br>• **분기·반기·사업보고서 발표 시 전면 리빌드 (`Track A`)**<br>• **Global/Weekly Trend 반영 격주 핀셋 델타 점검 (`Track B`)**<br>• **3축 구조적 병목 리드타임 및 K-주주환원·거버넌스 심층 해독** | • Track A: **`1.5% ~ 2.5%`**<br>• Track B: **`0.8% ~ 1.5%`**<br>*(기존 13% 대비 90% 절감)* |
| **⚡ 2순위 모델 (`Tier-2`)**<br>*고속 구조화 추론·준비 모델* | **`Gemini 3.8 Flash High`**<br>*(향후 `Argon Flash` 등 후속작)* | • **신규 기업 폴더 생성 및 초기 세팅 (`init`)**<br>• **`주가 = (수급 + 실적) × 기대감` 과거 데이터 역추적 & 4등급 기대감 테마 선별**<br>• **2-Step 극한 쿼터 절약 분업 시 `[Step 1: 공시 스캔 + prep 실행]`**<br>• **단순 최신 주가 기준 SOP 타점 리프레시 & 보유 종목 모바일 요약본 동기화** | • 폴더생성/SOP갱신: **`0.1% ~ 0.3%`**<br>• 과거역추적: **`0.4% ~ 0.8%`** |

---

## 🔍 Phase 1: 기업 해독기 (`Phase1_Report.md`) 표준 구조 및 필수 게이트

### 📋 Phase 1 필수 섹션 구성 (전 섹션 무생략 작성)
- **상단 헤더**: `💡 [핵심 용어 3줄 직관 해설]` + 단일 기준 주가(`anchor_price`) + 지배주주 귀속률(%) + `[글로벌 트렌드 매칭: 게이트 ①/②/③ 또는 N/A 뱃지]`
- **Section 1. 비즈니스 모델(BM) 해부 및 밸류체인 Mermaid 구조도** (Mermaid v10.9.8 문법 준수: 특수문자 노드명 큰따옴표 `id["텍스트(괄호)"]`, 파이프 라벨 `-->|"텍스트"|`, 영문 서브그래프 ID `subgraph SG1["한글제목"]`)
- **Section 2. 제품/사업부문별 매출 구성 및 `[Step 1.2] S-Curve 10% 변곡점 · 3축 구조적 병목(Capa·기술·특허) · 해소 리드타임 진단표`**
  - `2.1 S-Curve 신기술 테마 매출 익스포저 산출표`와 함께 `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 1-B] Step 1.2 S-Curve 10% 변곡점 · 3축 구조적 병목(Capa·기술·특허) · 리드타임 & Step 1.8 K-주주환원 진단표 (v4.3)`** 블록을 원형 그대로 삽입하고 다음 3대 질문을 심층 해독합니다 (세부 수리 명세는 [`s_curve_spec.md`](file:///e:/antigravity-work/my-skill/korean-stock-analyzer/s_curve_spec.md) 참조):
    1. **[질문 1 — 10% 침투율 변곡점]**: 전방 시장 내 기술 침투율이 **`8.0% ~ 18.0%` 골든 변곡점(Zone A)**에 진입했는가? (또는 1차 침투율이 성숙기라도 2차 S-Curve 차세대 공정 침투율이 10% 언저리인가?)
    2. **[질문 2 — 3축 구조적 병목 유발 여부]**:
       - **축 A (물리적 생산 Capa 병목)**: DART 가동률 `≥ 85~95%` 풀가동 또는 수주잔고 급증으로 물리적 공급 부족이 발생하는가?
       - **축 B (기술격차 해자)**: 독점적 공정/수율 격차로 영업이익률(OPM) `≥ 18~25%` 및 단가 전가력(Pricing Power)을 보유했는가?
       - **축 C (원천특허 · 글로벌 고객사 퀄 락인)**: 핵심 특허 또는 글로벌 Top-Tier 고객사 인증(Qualification)으로 후발주자 진입을 차단했는가?
    3. **[질문 3 — 병목 해소 예상 소요기간(Lead Time)]**: 경쟁사 증설·장비 리드타임·고객사 인증 통과까지 걸리는 물리적 시간이 **`≥ 24개월 (S등급 장기 병목)`**인가, **`12~23개월 (A등급 중기 병목)`**인가, **`< 12개월 (B등급 단기 병목)`**인가?
    4. **[질문 4 — S-Curve 3대 매도·디레이팅 시그널 & 노이즈 차단 가드레일 (v5.1 양방향 목표주가 반영)]**:
       - S-Curve는 매수 할증(`+6~26%`)만 주는 단방향 지표가 아니라, **3대 매도·디레이팅 시그널 발동 시 S-Curve 할증을 100% 박탈(`0%`)하고 `🚀 대안 A` 목표주가를 하향 디레이팅(`Base -5%~-15% / Bull -7%~-18%`, `PEG 0.65~0.70`)하며 Track 2 돌파매수를 차단**합니다:
       - **시그널 ① 쇼티지 해소 / 리드타임 축소 (`--shortage-easing`)**: 리드타임 `<12개월` 축소 & 가동률 `<70%` 하락(자동 감지) 또는 경쟁사 퀄 통과(Dual-Vendor 전환)·단가 인하 공시 확정 시 **`Base -6.0% / Bull -8.0%` 할인**.
       - **시그널 ② 침투율·실적 성장 기울기 둔화 (`--slope-decel`, 2차 도함수 음전환)**: 계절성 노이즈를 차단하기 위해 **[침투율 `≥25%` 성숙기 + 최근 4분기 영업이익 YoY 정점(`≥+40%`) 대비 `-50%p` 이상 급락 + 직전 분기 영업이익 `QoQ ≤ -15.0%` 동시 충족]** 시 자동 발동(또는 전방 침투율 YoY 증가폭 2분기 연속 축소 팩트 확인 시) ➔ **`Base -5.0% / Bull -7.0%` 할인**.
       - **시그널 ③ 정책·보조금 축소 및 관세·규제 역풍 (`--policy-headwind`)**: 뉴스 루머 노이즈를 배제하고 정부/의회/공시로 **확정된** 보조금 삭감·관세 부과·규제 역풍 시에만 발동 ➔ **`Base -7.0% / Bull -10.0%` 할인** (복합 발동 시 최대 하한 캡 `Base ×0.85 / Bull ×0.82` 적용).
- **Section 3. 재무 건전성 및 `[Step 1.5] 장부가(Book Value) 구성 해부 & SOTP 20% 분리 게이트`**
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 1] SOTP 장부 분해 & 4대 레짐 체크 요약표`**를 원형 그대로 삽입하고, 비영업자산 비중(`≥20%` 시 SOTP 분리 평가)과 본업 영업이익·Core ROIC 유지력을 해부합니다.
- **Section 4. 원가 구조, 영업 레버리지 및 가동률/수주잔고 실측**
- **Section 5. 자본 배분(CapEx, R&D) 및 `[Step 1.8] K-마켓 특수성 · 주주환원 입체 스코어카드`**
  - **5대 한국 시장 특수성 고정 점검**: ① 조세특례제한법 고배당 기업 배당소득 분리과세 적격성(배당성향 25%+ & 3년 평균 대비 배당 확대), ② 자사주 소각 완료 후 '주주환원 절벽(Post-Buyback Cliff)' 리스크, ③ 지배주주 사익편취(오너 개인회사 특수관계자 내부거래 터널링) 및 행동주의 이력, ④ 최대주주 지분율·가업승계 구도, ⑤ 메자닌(CB/BW/RCPS) 리픽싱 및 풋옵션 오버행.
- **Section 6. 핵심 리스크 요인 및 `[Step 3.5] 리스크 간 인과단계(Domino Chain) 구조도`** (`1차 촉발 ➔ 2차 영업·운전자본 전이 ➔ 3차 재무·자본 타격`)
- **Section 7. 4대 업종별 표준 실적 산출 공식 트리 (유형 A 연속공정 / B 수주장비 / C 플랫폼·에이전시 / D 브랜드 소비재)**
- **Section 8. `[Step 2.0] 4대 레짐 변화 고정 체크` & 최적 밸류에이션 지표 10년 백테스트** (1순위 채택 지표를 Phase 3 주 멀티플로 강제 상속)

---

## 📖 Phase 2: 스토리 리더 (`Phase2_Story.md` & `thesis_log.md`) 표준 구조 및 반증 게이트

1. **S-Curve 앵커 키워드 실측 대조 (`No-Blind-Citation`)** 및 **Step 1.2 3축 병목 · 리드타임 심층 검증 섹션 의무 수록**.
2. **포퍼식 가설 반증(Falsification) & 직전 분기(QoQ) 6열 표준 테이블 의무화**:
   - 모든 가설은 `[가설 ID (기록일) | 핵심 투자 가설 | 📊 직전 분기 대비 (QoQ) 실측 추이 | ✅ 확인 근거 (Bullish Fact) | 🚨 반증/약화 조건 (Kill-Switch) | 판정 상태]` 6열 규격을 준수합니다.

---

## 🎯 Phase 3: 가격 판독기 (`Phase3_DCF.md`) 표준 구조 및 필수 게이트

### 📋 Phase 3 필수 섹션 구성
- **Section 1. 역DCF 정밀 판독 (Equity · EV · SOTP 본업EV · 증설기 오너정규화 FCF 병기)**
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 1-C] Phase 3 Section 1 역DCF 3단 요구성장률 요약표`**를 원형 그대로 삽입하고 시장 내재 기대치를 판독합니다.
- **Section 2. 가치함정 이원화 판정(유형 A vs 유형 B) & 4대 레짐 변화 종합 판독**
- **Section 3. 시나리오 밸류에이션 (`🛡️대안 B | 🚀대안 A`) & `[Step 3.0] 사이클 피크 함정 차단` & `레드팀 역산 Capa 천장 검증`**
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 2] Phase 3 6열 시나리오 밸류에이션 표`**를 원형 그대로 삽입하고(시나리오 가정 칼럼만 서술), **레드팀 역산 내재 영업이익(`implied_op_base_a_eok`, `implied_op_bull_a_eok`)이 물리적 설비 Capa 상한을 초과하지 않는지** 검증합니다.
- **Section 3.5. 비관론자 반론(Pre-mortem) & 리스크 도미노(1차➔2차➔3차) 연쇄 시나리오 및 가설 Kill-Switch 점검**
- **Section 4. 마스터 SOP 실전 액션 플랜 (3분할 매수가 · 이중 안전핀 · 분할 익절) & 인터랙티브 계산기 태그**
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 2-B] Phase 3 Section 4 마스터 SOP 3분할 매수가 & 2단계 안전핀 실행표`**와 **`### 📌 [코드 자동 생성 3] HTML 계산기 직결 태그`**(`<div id="dcf-calculator-root" ...></div>`)를 원형 그대로 삽입합니다.

---

## 🔬 스페셜 애드온 모듈: `주가 = (수급 + 실적) × 기대감` 과거 데이터 역추적 & 기대감 테마 선별 프로토콜 (`Tier-2: 3.8 Flash High` 최적화)

이미 Phase 1~3 보고서가 작성된 기업에 대해 사용자가 **`"[기업명] 주가=(수급+실적)*기대감 관점으로 과거 데이터 분석해줘"`**를 입력하면 다음 4대 가드레일에 따라 분석 후 **`Weekly_Trend/company_timeline.md`**와 **`Weekly_Trend/thesis_log.md`**에 영구 업데이트합니다:

1. **SSOT 숫자 100% 고정 바인딩 (암산 금지)**: `2_Translated_DB/ai_prep_digest.md`(또는 `valuation_metrics.json`)와 `Phase1~3.md`, `1_Raw_Data/`의 실측 수치만 인용합니다.
2. **3단계 고정 마크다운 스키마 출력 강제**:
   - **[Step A] 과거 주요 주가 국면별 `(수급 + 실적) × 기대감` 3요소 분해표** (최소 3~5개 국면: 주가·멀티플 궤적 / 📈실적 Q·P·C·가동률 / 💰수급 외인·기관·자사주·증자·CB / 🔥기대감 멀티플 확장·수축 내러티브)
   - **[Step B] 기대감 자극 핵심 테마 4대 등급 선별 매트릭스**:
     - `👑 1순위: 핵심 리레이팅 테마 (Core Re-rating Theme)`
     - `🚀 2순위: 차세대 S-Curve 발화 테마 (Next S-Curve Ignition Theme)`
     - `🎁 3순위: 0원 무상 콜옵션 테마 (Free Call-Option Theme — 단독매출 <30% 시 추격매수 금지)`
     - `❌ 4순위: 가짜 · 소멸 · 피크아웃 테마 (Fake / Exhausted Theme — 재부각 시 익절 기회 활용)`
   - **[Step C] 현재 주가 위치의 `(수급 + 실적) × 기대감` 종합 진단 및 실전 시사점**
3. **영구 장부 분리 파일 쓰기 강제**:
   - `Weekly_Trend/company_timeline.md` 하단에 `## 📊 [심층 부록] 주가 = (수급 + 실적) × 기대감 과거 데이터 역추적 & 기대감 테마 선별` 섹션을 추가/갱신하고,
   - `Weekly_Trend/thesis_log.md` 6열 포퍼식 가설 표에 선별된 핵심 테마별 발화 트리거 및 반증 조건(Kill-Switch)을 등록합니다.

---

## ✅ 최종 출력 직전 핀셋 자가 검증 게이트 (`ksa_orchestrator.py build --patch-ssot`)
모든 보고서 작성 및 델타 업데이트의 마무리는 반드시 `python e:\antigravity-work\my-skill\korean-stock-analyzer\ksa_orchestrator.py build --corp-name [기업명] --patch-ssot` 실행 결과 **`[PASS]`** 확인으로 종료합니다(모바일 통합요약본은 별도 요청 시에만 `'holding'` 종목 한정으로 `generate_mobile_summary.py` 실행).
