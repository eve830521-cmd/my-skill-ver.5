---
name: korean-stock-analyzer
description: 한국 상장기업 DART 공시 및 글로벌 산업 딥리서치 기반 3-Phase 심층 가치평가 · 원샷 오케스트레이터(ksa_orchestrator.py) · 2-Tier 스마트 무손실 원문 발췌 · SOTP · S-Curve 10% 변곡점 · 3축 구조적 병목(Capa·기술·특허) · Step 1.3 BM 핵심인자·영업레버리지(DOL)·선행 OP 기울기 & 3중 안티-피크아웃 · K-주주환원스코어카드 · 레짐체크 · 사이클함정차단 · 주가=(수급+실적)*기대감 과거역추적 · 2-Tier 모델 커스텀 마스터 스킬 (v5.2)
---

# 🏛️ Korean Stock Analyzer 마스터 워크플로우 & 템플릿 규격서 (`SKILL.md` v5.2)

이 스킬은 한국 상장기업의 본원적 가치와 실전 매매 타점을 도출하기 위한 **단일 표준 규격서(v5.2)**입니다.
모든 분석은 **『1순위: 보고서 퀄리티 및 수리·회계·논리적 무결성 100% 사수 / 2순위: 원샷 오케스트레이터(`ksa_orchestrator.py`) 기반 토큰·쿼터 소모량 90% 절감(65회 도구 호출 ➔ 4~6회 압축)』** 대원칙을 따릅니다.

---

## ⚡ 제0원칙: v5.2 원샷 오케스트레이터(`ksa_orchestrator.py`) & 4~6턴 완결 파이프라인 규율

과도한 도구 호출(`read_file` 30회, 개별 파이썬 실행 24회)로 주간 한도 13%가 소모되던 문제를 원천 해결하기 위해, 에이전트는 반드시 아래 **4단계 원샷 실행 프로토콜**을 준수해야 합니다:

### 1. [Step 1 — 원샷 준비 명령 (`run_command` 단 1회) & 직전 vs 신규 SSOT 비교표 승인]
- `backtest_valuation.py`, `calc_reverse_dcf.py`, `parse_pdf.py`를 개별적으로 여러 번 실행하지 마십시오.
- `korean-dart` MCP(`search_disclosures`)로 최근 공시를 스캔하고 `1_Raw_Data`/신뢰 리포트에서 **DART `비용의 성격별 분류`(고정비율·변동비율)·가동률 추이·변동비 추이·BM 핵심인자·선행 OP 기울기(`Step 1.3`)**를 함께 점검한 직후, 아래 **`ksa_orchestrator.py prep` 명령 단 1회**로 ① 4대 폴더 초기화, ② 기존 SSOT 파라미터 자동 계승, ③ 10년 백테스트 & SOTP/병목/Step 1.3 BM 선행 OP 기울기/K-주주환원 연산, ④ 역DCF 3단 요구성장률 연산, ⑤ 2-Tier 스마트 무손실 PDF 원문 발췌(`verbatim_extracts.md`, 비판/리스크 25% + 비용·가동률 20% 쿼터 보장, 최대 18쪽 캡), ⑥ **단일 통합 브리핑(`ai_prep_digest.md`) + `[직전 vs 신규 SSOT 비교표]`(`ssot_diff_summary.md`) 생성**을 한 번에 완료합니다:
  ```powershell
  python e:\antigravity-work\my-skill\korean-stock-analyzer\ksa_orchestrator.py prep --corp-name [기업명] [--code 종목코드] [신규/변경 파라미터만 추가]
  ```
  - **주요 옵션 (변경 시에만 입력, 미입력 시 기존 `valuation_metrics.json` 저장값 자동 계승)**:
    `--sector-type [A/B/C/D] --distb-shares [유통주식수] --total-shares [총주식수] --fcf [보고FCF억] --norm-fcf [오너정규화FCF억] --non-op-assets [비영업자산억] --net-debt [순차입금억] --rerating-date [YYYY-MM-DD] --dart-exposure [신기술매출비중%] --forward-eps [추정EPS] --forward-eps-g [EPS성장률%] --expected-dps [배당금] --penetration-pct [1차침투율%] --second-penetration-pct [2차침투율%] --bottleneck-grade [S/A/B/C] --bottleneck-months [리드타임개월] --capa-util-pct [가동률%] --shortage-easing --slope-decel --policy-headwind --clear-sell-signals --bm-core-driver "[BM핵심인자]" --fixed-cost-ratio [고정비율%] --var-cost-ratio [변동비율%] --util-trend [up/flat/down] --var-cost-trend [down/flat/up] --op-slope [strong_accel/accel/neutral/decel/contraction] --slope-evidence [high/medium/low] --capa-expand --asp-up --clear-bm-slope --value-trap --no-value-trap --clear-value-trap --payout-ratio [배당성향%] --tsr-pct [총주주환원율%] --buyback-cliff --mezzanine-eok [메자닌잔액억] --mezzanine-pct [희석률%] --related-party-eok [내부거래억] --listed-parent-sales --governance-discount [할인율%] --gov-note "[지배구조주석]" --primary-keywords "핵심어1,핵심어2" --keywords "테마어1,테마어2"`
  - **[Step 1.5 — 가치함정 경보(`⚖️ A/B 분리 판독`) 발생 시 사용자 확정 스위치 선택 (v5.2.2)]**:
    - 기본값(`value_trap_override=None`)은 진짜 가치함정 방어를 위해 **A/B 분리 판독(`dual_split_review`)**을 유지합니다 (`🛡️대안 B` = 유형 B 가치함정 보수 닻 & SOP 매수 보류 vs `🚀대안 A` = 5년 60M 사이클 PBR 정상화 + Step 1.3 영업레버리지).
    - `[직전 vs 신규 SSOT 비교표]` 10초 검수에서 `⚖️ A/B 분리 판독`이 감지되면, 기업 스터디 후 **일시적 선투자·사이클 저점으로 비함정 통일 시 `--no-value-trap`**(`🔄 유형 A-2 확정`: B·A안 및 SOP 모두 5년 사이클 정상화), **진짜 구조적 가치함정 확정 시 `--value-trap`**(`🔴 유형 B 확정`: B·A안 및 SOP 모두 청산가치 하단 잠금), **초기화 시 `--clear-value-trap`**으로 `prep --skip-pdf`를 1회 재실행합니다(확정 스위치 값은 `valuation_metrics.json`에 영구 계승).

### 2. [Step 2 — 단일 통합 브리핑 로드 (`read_file` 단 1회)]
- `auto_tables.md`, `valuation_metrics.json`, `thesis_log.md`, `company_timeline.md`, `verbatim_extracts.md`를 각각 따로 `read_file` 하지 마십시오.
- 오직 **`Stock_Research/[기업명]/2_Translated_DB/ai_prep_digest.md` 파일 단 1개만 `read_file`로 읽으십시오.**
- 이 파일 안에 트랙 판정(`Track A` vs `Track B`), 코드 확정 마크다운 표 7종(`코드 자동 생성 1, 1-B, 1-C, 1-D, 2, 2-B, 2-C, 3`), 기존 6열 가설 및 타임라인, 그리고 2-Tier 필터링된 무손실 PDF 원문 발췌본이 모두 통합되어 있습니다.

### 3. [Step 3 — Track A(전면 작성) vs Track B(격주 핀셋 델타) 분기 실행]
- **⚠️ 절대 저장 경로 고정 (경로 이탈 시 `validate_report.py` 즉시 `[FAIL]`)**:
  - 모든 보고서는 반드시 **`Stock_Research/[기업명]/3_Final_Reports/Phase1_Report.md`**, **`3_Final_Reports/Phase2_Story.md`**, **`3_Final_Reports/Phase3_DCF.md`**에 저장하며, 가설·타임라인은 **`Stock_Research/[기업명]/Weekly_Trend/thesis_log.md`** 및 **`company_timeline.md`**에 저장합니다.
  - 기업 루트(`Stock_Research/[기업명]/Phase*.md`)나 임의 폴더(`3_Reports/` 등)에 보고서 파일을 생성·저장하는 행위를 절대 금지합니다.
- **🏛️ Track A (`신규 기업 최초 분석` / `분기·반기·사업보고서 신규 발표` / `빅 이벤트` / `구버전 v4.x 클린 리빌드`)**:
  - `ai_prep_digest.md` 최상단 `PART D`의 **Phase 1~3 고정 표준 목차 스켈레톤(`## 1.`~`## 8.`)**을 전 종목 100% 동일하게 적용하고, `[코드 자동 생성 1, 1-B, 1-C, 1-D, 2, 2-B, 2-C, 2-D, 3]` 표를 **단 1원도 AI가 임의로 수정하지 않고 그대로 삽입**하여 위 `3_Final_Reports/` 고정 경로에 각각 독립된 `write_file` 호출로 무생략 작성합니다.
- **⚡ Track B (`격주 Global/Weekly Trend 점검` / `수시 공시·주가 반영 업데이트` — 이미 v5.0/v5.1 게이트 및 표준 목차가 완비된 기업)**:
  - **🚫 절대 금지**: 2주 만에 바뀌지 않는 `3_Final_Reports/Phase1_Report.md`나 `Phase3_DCF.md` 전체를 다시 쓰거나(`write_file`), 단순 주가·목표가·매수가 숫자를 고치기 위해 `Phase1`·`Phase3`를 읽고 수동 편집하지 마십시오!
  - **✅ AI 전담 작업 (도구 호출 2~3회)**:
    1) `ai_prep_digest.md`의 신규 PDF 원문 발췌본과 최신 공시를 바탕으로 **`Weekly_Trend/company_timeline.md`**와 **`Weekly_Trend/thesis_log.md`(6열 포퍼식 가설 표)**를 `edit_file`로 핀셋 업데이트합니다.
    2) 핵심 서사나 리드타임 가정이 추가된 경우에만 `3_Final_Reports/Phase2_Story.md`(또는 `3_Final_Reports/Phase3_DCF.md` 시나리오 서술 칼럼)의 해당 문단을 `edit_file`로 보강합니다.
    3) `3_Final_Reports/Phase1_Report.md`와 `Phase3_DCF.md`의 모든 주가·시총·멀티플·역DCF·목표가·3분할 매수가·안전핀·HTML 계산기 태그는 **Step 4의 `build --patch-ssot` 명령이 파이썬 코드로 100% 자동 치환**합니다!

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
| **👑 1순위 모델 (`Tier-1`)**<br>*최상위 심층 추론 모델* | **`Gemini 4 Neon (High)`**<br>*(향후 4.5/5.0 Pro·Ultra 후속작)* | • **신규 기업 최초 Phase 1~3 심층 분석 (`Track A`)**<br>• **분기·반기·사업보고서 발표 시 전면 리빌드 (`Track A`)**<br>• **Global/Weekly Trend 반영 격주 핀셋 델타 점검 (`Track B`)**<br>• **3축 구조적 병목 리드타임 및 K-주주환원·거버넌스 심층 해독** | • Track A: **`1.5% ~ 2.5%`**<br>• Track B: **`0.8% ~ 1.5%`**<br>*(기존 13% 대비 90% 절감)* |
| **⚡ 2순위 모델 (`Tier-2`)**<br>*고속 구조화 추론·준비 모델* | **`Gemini 4 Hydrogen (High)`**<br>*(향후 4.5/5.0 Flash 후속작)* | • **신규 기업 폴더 생성 및 초기 세팅 (`init`)**<br>• **`주가 = (수급 + 실적) × 기대감` 과거 데이터 역추적 & 4등급 기대감 테마 선별**<br>• **2-Step 극한 쿼터 절약 분업 시 `[Step 1: 공시 스캔 + prep 실행 / --no-value-trap 스위치 확정]`**<br>• **단순 최신 주가 기준 SOP 타점 리프레시 & 보유 종목 모바일 요약본 동기화** | • 폴더생성/SOP갱신: **`0.1% ~ 0.3%`**<br>• 과거역추적: **`0.4% ~ 0.8%`** |

---

## 🔍 Phase 1: 기업 해독기 (`3_Final_Reports/Phase1_Report.md`) 표준 구조 및 필수 게이트

### 📋 Phase 1 필수 섹션 구성 (전 종목 `## 1.`~`## 8.` 고정 헤딩 스켈레톤 강제 · 무생략 작성)
- **구조 통일 규율**: 모든 기업의 `3_Final_Reports/Phase1_Report.md`는 `static_cache_prefix.md` `PART D`에 정의된 **`## 1.` ~ `## 8.` 고정 섹션 번호·순서**를 100% 동일하게 유지해야 하며(임의 섹션 재배치·누락 금지), 최상단 H1 제목에 `(v5.2)`를 표기합니다(`v4.x` 헤더 잔존 또는 `## 1.`~`## 8.`/`Step 1.3` 누락 시 `validate_report.py` 즉시 `[FAIL]` 및 `Track A` 클린 리빌드 강제).
- **상단 헤더**: **`> **분석완료일**: YYYY-MM-DD`** (Phase 1·2·3 전 보고서 최상단 제목 직하단 필수 고정 — `build --patch-ssot`가 자동 동기화, HTML `<title>`은 `[기업명] [Phase] — Stock Analyzer Report (v5.0)` 통일) + `💡 [핵심 용어 3줄 직관 해설]` + 단일 기준 주가(`anchor_price`) + 지배주주 귀속률(%) + `[글로벌 트렌드 매칭: 게이트 ①/②/③ 또는 N/A 뱃지]`
- **Section 1. 비즈니스 모델(BM) 해부 및 밸류체인 Mermaid 구조도** (Mermaid v10.9.8 문법 준수: 대괄호·소괄호·콜론 포함 노드명 큰따옴표 `id["텍스트[보조]"]`, 파이프 라벨 `-->|"텍스트"|`, 영문 서브그래프 ID `subgraph SG1["한글제목"]`, **단독 소문자 `end` 노드 ID 절대 금지 — `END_NODE` 등 사용**)
- **Section 2. 제품/사업부문별 매출 구성 및 `[Step 1.2] S-Curve 10% 변곡점 · 3축 구조적 병목(Capa·기술·특허) · 해소 리드타임 진단표`**
  - `2.1 S-Curve 신기술 테마 매출 익스포저 산출표`와 함께 `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 1-B] Step 1.2 S-Curve 10% 변곡점 · 3축 구조적 병목(Capa·기술·특허) · 리드타임 & Step 1.8 K-주주환원 진단표 (v5.0)`** 블록을 원형 그대로 삽입하고 다음 3대 질문을 심층 해독합니다 (세부 수리 명세는 [`s_curve_spec.md`](file:///e:/antigravity-work/my-skill/korean-stock-analyzer/s_curve_spec.md) 참조):
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
- **Section 4. 원가 구조, 영업 레버리지 및 `[Step 1.3]` BM 연계 영업이익 핵심인자 · 선행 OP 기울기 진단 (★v5.2.3 핵심)**
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 1-D] Step 1.3 비즈니스 구조 연계 영업이익 핵심인자 · 영업레버리지(DOL) · 선행 OP 기울기 진단표`**를 원형 그대로 삽입합니다(`④-B KR-DOL 연속 배율` · `④-C KR-컨센서스 이중가산 흡수` 행 포함).
  - DART 주석 **`비용의 성격별 분류`**(고정비율: 감가상각·고정인건비 vs 변동비율: 원재료·외주가공·변동판관비)로 공헌이익률(`CM%`)과 이론 영업레버리지(`DOL = CM% / OPM%`)를 산출하고, **4대 업종별 핵심인자**(유형 A/B: 고정비율·가동률 추이·변동비율·수주잔고 / 유형 C: 인건비·트래픽 레버리지·ARPU / 유형 D: 수출 ASP 믹스·원가/마케팅비율)가 향후 2~4분기 **영업이익 기울기(가속 `strong_accel`/`accel` vs 유지 `neutral` vs 둔화·역성장 `decel`/`contraction`)**를 어떻게 바꾸는지 BM 구조와 연계해 논증합니다.
  - **KR-DOL 연속 배율 (v5.2.3)**: `quant_driver_synthesis` 모드 한정으로 기준 `DOL 2.5배` 대비 `0.60x~1.40x` 연속 보정하며(DART TTM 회귀 DOL은 환율 노이즈 감안 편차 50% 반영·상방 `1.20x` 캡, `OPM < 5%` 구간은 상방 증폭 차단·하방 역레버리지 증폭 유지), 최종 계수는 상·하한(`Base 0.88~1.12` / `Bull 0.85~1.15`) 내에서 산출됩니다.
  - **3중 한국형 안티-피크아웃 가드레일 점검**: ① 제조/장치주 가동률 `≥ 92%` 물리적 천장(무증설·무ASP인상 시 상방 할증 차단, QoQ 꺾임 시 감속 강등), ② 주가 선반영 과열(역DCF EV `>+15%` / 3Y PBR 90% / 주봉 MFI 과열 시 상방 할증 50~100% 축소), ③ 공시·리포트 근거 신뢰도 등급(`high`/`medium`/`low`) 캡 적용 결과를 해독합니다.
- **Section 5. 자본 배분(CapEx, R&D) 및 `[Step 1.8] K-마켓 특수성 · 주주환원 입체 스코어카드 (v5.0)`**
  - **5대 한국 시장 특수성 고정 점검 (`[1-B]` ④-A/B/C 3단 직결)**: ① `④-A` 조세특례제한법 고배당 분리과세 적격성(배당성향 `25%+` & 배당 확대, `--payout-ratio` 우선 판정) + DPS + 총주주환원율(`--tsr-pct`), ② `④-B` 자사주 소각 후 주주환원 절벽(`--buyback-cliff`) 및 메자닌(CB/BW/RCPS) 잠재 희석 오버행(`--mezzanine-eok`, `--mezzanine-pct`), ③ `④-C` 상장 모회사 정상 영업유통(`--listed-parent-sales`, 터널링 0%) vs 오너 개인회사 사익편취 내부거래 분리·거버넌스 할인(`--governance-discount`, `--gov-note`, SSOT 영구 계승·중복할인 차단).
- **Section 6. 핵심 리스크 요인 및 `[Step 3.5] 리스크 간 인과단계(Domino Chain) 구조도`** (`1차 촉발 ➔ 2차 영업·운전자본 전이 ➔ 3차 재무·자본 타격`)
- **Section 7. 4대 업종별 표준 실적 산출 공식 트리 (유형 A 연속공정 / B 수주장비 / C 플랫폼·에이전시 / D 브랜드 소비재)**
- **Section 8. `[Step 2.0] 4대 레짐 변화 고정 체크` & 최적 밸류에이션 지표 10년 백테스트** (1순위 채택 지표를 Phase 3 주 멀티플로 강제 상속)

---

## 📖 Phase 2: 스토리 리더 (`Phase2_Story.md` & `thesis_log.md`) 표준 구조 및 비판적 수용·반증 게이트

0. **상단 헤더**: **`> **분석완료일**: YYYY-MM-DD`** + 단일 기준 주가(`anchor_price`)를 최상단 제목 직하단에 반드시 명기합니다(`--patch-ssot` 시 자동 동기화).
1. **Global Trend 및 외부 딥리서치 '비판적 수용(Critical Verification)' 3대 규율**:
   - **무조건적 수용 금지**: 증권사 리포트(Sell-Side)의 장밋빛 수요 전망·목표주가를 그대로 수용하지 않으며, 반드시 **① DART 실측 가동률·수주잔고·단독 매출 비중(≥30% 미만 시 무상 콜옵션 `pen_base_boost = 0%` 강제 차단) 대조**, **② `parse_pdf.py`가 의무 발췌한 `[⚖️비판·리스크검증]` 페이지(공급과잉·단가인하·수율한계·스트레스 테스트·LTA 해지선 등) 교차 검증**, **③ 레드팀 역산 Capa 천장 검증**을 통과한 팩트만 채택합니다.
2. **S-Curve 앵커 키워드 실측 대조 (`No-Blind-Citation`)**, **Step 1.2 3축 병목 · 리드타임 심층 검증**, 및 **Step 1.3 BM 핵심인자(가동률·변동비·수주/ASP) 선행 OP 기울기 교차검증** 의무 수록.
3. **포퍼식 가설 반증(Falsification) & 직전 분기(QoQ) 6열 표준 테이블 의무화**:
   - 모든 가설은 `[가설 ID (기록일) | 핵심 투자 가설 | 📊 직전 분기 대비 (QoQ) 실측 추이 | ✅ 확인 근거 (Bullish Fact) | 🚨 반증/약화 조건 (Kill-Switch) | 판정 상태]` 6열 규격을 준수하며, 5번째 열(`Kill-Switch`)에 **Step 1.3 BM 핵심인자 기울기 둔화 임계치(예: 가동률 하한, 변동비율 상한, 수주 B/B)**를 반드시 직결합니다.

---

## 🎯 Phase 3: 가격 판독기 (`Phase3_DCF.md`) 표준 구조 및 필수 게이트

### 📋 Phase 3 필수 섹션 구성
- **상단 헤더**: 최상단 제목 직하단에 **`> **분석완료일**: YYYY-MM-DD | **단일 기준 주가 (Anchor Price)**: ...`**를 명기합니다(`--patch-ssot` 시 `작성 기준일`도 `분석완료일`로 자동 통일).
- **Section 1. 역DCF 정밀 판독 (Equity · EV · SOTP 본업EV · 증설기 오너정규화 FCF 병기)**
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 1-C] Phase 3 Section 1 역DCF 3단 요구성장률 요약표`**를 원형 그대로 삽입하고 시장 내재 기대치를 판독합니다.
- **Section 2. 가치함정 삼원화 판정(유형 A / 유형 A-2 / 유형 B · `⚖️ A/B 분리 판독` · `Core NOPAT ROE` 착시 차단) & 4대 레짐 변화 종합 판독 (v5.2.2)**
  - **일회성 법인세수익·영업외손익 ROE 착시 차단 (`roe_non_op_distortion`)**: `표면 ROE - 본업 NOPAT ROE ≥ 3.0%p` & `표면 ≥ 8.5%` & `본업 < 8.5%` 시 가치함정·수익성 판정에 **본업 NOPAT ROE 및 본업 2년 OP 증감률**을 우선 적용합니다.
  - **기본 동작 = `⚖️ A/B 분리 판독 (dual_split_review)` (진짜 가치함정 방어 유지)**: 경보(`고점 PBR ≥ 2.8x` + `2년 이익 ≤ -30%` + `ROE < 8.5%`) 감지 시 기계적 단정을 피하고 **`🛡️ 대안 B`(유형 B 가치함정 보수 닻: 청산 PBR 0.70x / p20 / 3Y 평균 & SOP 매수 보류)**와 **`🚀 대안 A`(5년 60M 사이클 PBR 정상화 + Step 1.3 영업레버리지)**를 완전 분리 병기합니다.
  - **사용자 확정 스위치 (`--no-value-trap` / `--value-trap` / `--clear-value-trap`, SSOT 영구 계승)**:
    - **`--no-value-trap` (`🔄 유형 A-2 비함정 확정`)**: 스터디 후 일시적 선투자·사이클 저점으로 판단해 확정 시 **`🛡️ 대안 B` · `🚀 대안 A` · 마스터 SOP 모두 유형 B 페널티를 해제하고 5년(60M) 사이클 PBR 밴드로 통일 정상화**합니다(단, 분기 OP 급반등 `QoQ ≥ +15% & YoY ≥ +20%` 전 Track 2 추격매수는 차단).
    - **`--value-trap` (`🔴 유형 B 확정`)**: 진짜 구조적 가치함정으로 확정 시 **`🛡️ 대안 B` · `🚀 대안 A` · 마스터 SOP 모두 과거 호황 멀티플을 전면 폐기하고 청산 PBR 0.70x 하단 및 현재가 매수 금지(`is_value_trap_hold`)로 잠금** 처리합니다.
    - **`--clear-value-trap`**: 저장된 수동 확정을 초기화하여 기본 `⚖️ A/B 분리 판독`으로 복귀합니다.
- **Section 3. 시나리오 밸류에이션 (`🛡️대안 B | 🚀대안 A`) & `[Step 1.3 선행 OP 기울기 🚀대안 A 단독 반영]` & `[Step 1.5 SOTP 직결]` & `[Step 3.0 사이클 피크 함정 차단]` & `레드팀 역산 연간 내재 OP Capa 천장 검증`**
  - **A/B안 역할 절대 분리 (v5.2.3)**: `Step 1.3` BM 핵심인자 · 선행 OP 기울기 계수(`op_slope_mult`: `×0.88~×1.12` Base / `×0.85~×1.15` Bull, 기존 후행 `op_mult` 대체)는 **오직 `🚀 대안 A`에만 단독 반영**되며, **`🛡️ 대안 B`는 단 1원도 변경하지 않는 순수 DART 역사적 밴드 중심 닻**으로 보존하여 피크아웃·선반영 위험을 이중 방어합니다. 또한 `--forward-eps` 활성화(주봉 C등급 정지 제외) 시 내재 성장률 `+5~15%` 50% · `≥+15%`(또는 흑자전환) 100%를 대안 A 앵커 내 Forward EPS 가중치만큼 상방 할증에서 자동 흡수해 컨센서스 이중 가산을 차단합니다(하방 `decel`/`contraction` 할인 100% 유지 + **`Section 4 Track 2` 돌파매수 즉시 차단**).
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 2] Phase 3 6열 시나리오 밸류에이션 표`**를 삽입하되 **4~6열 숫자는 원형 고정하고, 3열 `핵심 드라이버 가정`의 `[AI 작성 필수: ...]` 플레이스홀더는 반드시 ① 전방 수요·고객사·핵심 제품 믹스/ASP 및 Step 1.3 BM 핵심인자(고정비 DOL·가동률·변동비율) 추이, ② 가동률·증설 Capa·연간 내재 영업이익/OPM 수치, ③ 멀티플 리레이팅·주주환원·Kill-Switch 촉발 조건으로 기업별 구체 서술 교체 필수**(`ksa_orchestrator.py build --patch-ssot` 실행 시 AI가 작성한 3열과 표 하단 요약 문단은 자동 보존되며, 미교체·일반문구 잔존 시 `validate_report.py`에서 즉시 `[FAIL]` 처리). 비영업자산 ≥ 20% 기업은 **SOTP 분리 주당가치(`본업 Core BPS × PBR + 비영업자산 안전가치`)**를 `Base/Bull` 산식에 직접 반영하며, **레드팀 역산 연간 내재 영업이익(`implied_op_base_a_eok`, `implied_op_bull_a_eok` — 저점 왜곡 PER 캡핑으로 `Bull ≥ Base` 보장)이 물리적 설비 Capa 상한을 초과하지 않는지** 검증합니다.
  - **추정치(`forward_eps`) · `[Step 3.0]` · `TP1` · `[2-D]` 일관성 가드레일 (`v5.1`)**:
    1) **주봉 `C등급` 하락추세 낙관치 차단 (`forward_eps_suspended`)**: `w_swing_grade == "C"` 구간에서는 추정 `forward_eps` · `forward_eps_g` 반영을 일시 정지하고 확정 **TTM EPS · 현행 BPS**로 회귀하여 하락 추세 중 추정치 기반 목표가 과대계상을 차단합니다.
    2) **`[Step 3.0]` 3요소 비과열 램프업 예외 (`is_non_overheated_rampup`)**: 유형 A·B 시클리컬이라도 **실적 가속(`QoQ ≥ +15%` & `YoY ≥ +20%` & TTM EPS 흑자·ROE ≥ 8.5%) + 기대감 비과열(역DCF EV 요구성장률 `≤ +12%`, 미산출/`None`일 때는 `PBR ≤ 3Y 평균` & `밴드 ≤ 50%`로 엄격 제한 & `PBR < 3Y p90 × 0.95`) + 수급 비과열(주봉 `MFI < 75` & 12주 최고 `MFI < 80`)**을 동시에 충족하면 피크 이익 캡을 면제하여 초입 램프업 저평가를 방지합니다.
    3) **`TP1` 순환참조 제거 & 반도체 소부장 듀얼 앵커 정렬 (`Base ≤ TP1 ≤ Bull` + `tech_resist_1`)**: `TP1` 산식에서 현재가 자기참조(`curr_price × 1.06`)를 제거하고, 급락 후 반등 구간(`52주 p75 > 60일 고가 p75 × 1.25`)은 60일 저항(60%)·52주 저항(40%)을 블렌딩해 옛 고점 착시를 완화합니다. 직전 매물저항(`tech_tp1_raw`)이 `Base` 하단이면 `TP1`을 `Base` 위에 억지로 띄우지 않고 **`TP1 = Base`로 고정**한 뒤 `tech_resist_1`을 선행 스윙 저항 체크선으로 별도 병기합니다.
    4) **`[코드 자동 생성 2-D]` KRX 외인·기관 순매수 결합 및 국면 정밀 분리**: 수급($S/D$) 축에 KRX 20일 외인·기관 수급비중/외국인지분율 변화를 결합하고, 실적 강세+단기 수급 눌림(`🌤️ 역배열·수급 눌림 vs 실적 우위형`)과 동반 약세(`🧊`), `TTM Base` 고평가 상태의 보유자 추세 보유(`💎 실적·수급 우위형 [FCF 거품 0%]`)를 명확히 분리 표기합니다.
- **Section 3.5. 비관론자 반론(Pre-mortem) & 리스크 도미노(1차➔2차➔3차) 연쇄 시나리오 및 가설 Kill-Switch 점검**
- **Section 4. 마스터 SOP 실전 액션 플랜 (주봉 C등급 칼날받기 차단 · 3분할 매수가 · 이중 안전핀 · 분할 익절) & 인터랙티브 계산기 태그**
  - **주봉 스윙 `C등급(<50점)` 역배열·매물벽 하단 저항 종목 현재가 매수 차단 (`is_downtrend_hold`)**: 목표주가 대비 저평가라도 주봉 추세가 `C등급`이면 `Buy2/Buy3`에 현재가(`curr_p`)를 배치하지 않고 **전 구간 하방 지지선(`Buy1 < Buy2 < Buy3 < 현재가 × 0.95`) 대기 또는 주봉 20주선 회복·MACD 양전환(B등급↑) 확인 후 진입**하도록 강제합니다.
  - `ai_prep_digest.md`의 **`### 📌 [코드 자동 생성 2-C]`**, **`### 📌 [코드 자동 생성 2-B] Phase 3 Section 4 마스터 SOP 3분할 매수가 & 2단계 안전핀 실행표`**, **`### 📌 [코드 자동 생성 3] HTML 계산기 직결 태그`**(`<div id="dcf-calculator-root" ...></div>`)를 원형 그대로 삽입합니다.

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

## ✅ 최종 출력 직전 핀셋 자가 검증 게이트 (`ksa_orchestrator.py build --patch-ssot`) & Ver.5 전담 푸시 규율
모든 보고서 작성 및 델타 업데이트의 마무리는 반드시 `python e:\antigravity-work\my-skill\korean-stock-analyzer\ksa_orchestrator.py build --corp-name [기업명] --patch-ssot` 실행 결과 **`[PASS]`** 확인으로 종료합니다(모바일 통합요약본은 별도 요청 시에만 `'holding'` 종목 한정으로 `generate_mobile_summary.py` 실행).
향후 v6으로 전면 리프레이밍하기 전까지 모든 GitHub 커밋 & 푸시 작업은 반드시 **`my-skill-ver.5` 저장소(`origin`)**로 수행하며, 기존 v4.3.2 최종본(`my-skill-Ver.4`)과 엄격히 분리하여 영구 보존합니다.
