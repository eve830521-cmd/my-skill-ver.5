# 🏛️ Korean Stock Analyzer v5.0 전면 리프레이밍 마스터 플랜 (`plan.md`)

> **작성일**: 2026-11-01  
> **최우선 원칙**: **1순위 = 보고서 퀄리티 및 수리·회계·논리적 무결성 극대화 (100% 보존 + 심화)** / **2순위 = 토큰·쿼터 소비 효율성 극대화 (65회 도구 호출 ➔ 4~6회 원샷 압축, 주간 한도 13% ➔ 1~2%대 절감)**  
> **대상 모델 체계**: **1순위 최상위 모델 (`Tier-1`: 현재 `Gemini 4.0 Argon Medium`, 후속 모델 커스텀 가능)** & **2순위 고속 구조화 모델 (`Tier-2`: 현재 `Gemini 3.8 Flash High`, 후속 `Argon Flash` 등 커스텀 가능)**

---

## 🔍 1. 기존 시스템(v4.3.2) 과도한 토큰 소모(13% / 275만 토큰) 5대 근본 원인 진단

직전 `티씨케이` 작업에서 디스크 파일을 정리했음에도 **총 102 스텝, 도구 호출 65회(`read_file` 30회, `run_command` 24회 등), 누적 275만 토큰(주간 한도 13.75%)**이 소모된 근본 원인은 **파이썬 도구들의 파편화**와 **PDF 키워드 발췌의 OR 폭발 현상**에 있었습니다:

| 근본 원인 | 기존(v4.3.2) 작동 방식의 문제점 | 토큰 낭비 규모 | v5.0 리프레이밍 핵심 해결책 |
| :--- | :--- | :---: | :--- |
| **① PDF 발췌 OR-키워드 폭발**<br>(`parse_pdf.py`) | `배당, NAND, HBM` 같은 광범위한 단어를 단순 OR 조건으로 검색하여, 무관한 손해보험·은행 리포트까지 17개 PDF 전체에서 **249페이지(17,391줄, 500KB)**를 `verbatim_extracts.md`로 덤프함. 이후 AI가 이를 읽으려 `read_file`을 20회 이상 분할 호출함. | **~120만 토큰**<br>(컨텍스트 폭발 주범) | **2-Tier 핀셋 스코어링 무손실 발췌 엔진 (`parse_pdf.py` v5.0)**:<br>• `1차 핵심어(기업명·코드·독점제품)` 매칭 페이지는 100% 최우선 전문 추출<br>• `2차 산업/테마 키워드`는 **동일 페이지 내 2개 이상 동시 출현(Co-occurrence)** 및 **비관련 섹터(보험·은행·유통 등) 배제 필터(`--exclude-keywords`)** 적용 + 적합도 상위 페이지(기본 20쪽 이내) 무손실 추출로 **249쪽 ➔ 10~15쪽(1회 `read_file` 완독 크기)으로 압축 (원문 무결성 100% 유지)** |
| **② 파편화된 파이썬 개별 호출**<br>(24회 `run_command`) | 폴더 생성, `backtest_valuation.py`, `calc_reverse_dcf.py`, `parse_pdf.py`, `generate_html.py`(×3회), `validate_report.py`를 각각 별도 터미널 명령으로 15~24번 쪼개서 호출함 (`호출 횟수 × 기본 컨텍스트` 눈덩이 누적). | **~80만 토큰** | **원샷 통합 오케스트레이터 (`ksa_orchestrator.py` 신설)**:<br>• **`prep` 명령 1회**: 폴더 초기화 + 기존 SSOT 파라미터 자동 계승 + `backtest` + `reverse_dcf` + `2-Tier PDF 무손실 발췌` + **`ai_prep_digest.md` (단일 통합 브리핑 문서) 생성**을 단 1번의 실행으로 끝냄.<br>• **`build` 명령 1회**: SSOT 수치 자동 패치(`--patch-ssot`) + Phase 1~3 HTML 3종 일괄 빌드 + `validate_report.py` 무결성 검증까지 단 1번의 실행으로 완결. |
| **③ Track B(격주 점검) 시 수동 숫자 패치 & 강제 리빌드** | 주가나 목표가만 바뀌는 격주 점검(Track B)에서도 AI가 직접 `Phase1`, `Phase3` 전체를 읽고 표 숫자를 수동 편집하거나, 구버전 게이트 누락 시 3.5만 자 전체를 백지 재작성(`write_file` 4회)함. | **~50만 토큰** | **코드 기반 결정론적 SSOT 패처 (`ksa_orchestrator.py build --patch-ssot`)**:<br>• `Phase1_Report.md`와 `Phase3_DCF.md` 내 코드 영역(`단일 기준 주가`, `[코드 자동 생성 1/1-B/2/3]`, 역DCF 표, SOP 매수가·안전핀 표)을 파이썬이 0.1초 만에 무결점 자동 치환.<br>• AI는 숫자를 수정하느라 `Phase1/3`을 읽거나 재작성할 필요 없이 오직 **신규 리포트 인과 추론 및 가설 심판(`thesis_log.md`, `company_timeline.md`, `Phase2_Story.md`)에만 100% 집중!** |
| **④ 상시 프롬프트(`GEMINI.md`) 및 `SKILL.md` 중복 서술** | 매 턴 기본 탑재되는 `GEMINI.md`(22KB)와 `SKILL.md`(40KB)에 동일한 설명이 장문으로 중복 기재되어 매 턴 기본 배낭 무게를 가중시킴. | **~25만 토큰** | **18대 무결성 원칙 100% 보존 + 고밀도 압축 리프레이밍**:<br>• 지금까지 시행착오를 거쳐 완성한 **18대 원칙(SOTP, 4대 레짐, Step 1.2 10%변곡점·3축병목·리드타임, Step 1.8 K-주주환원, 사이클 피크 캡, 레드팀 Capa 역산, 포퍼식 6열 Kill-Switch, 주가=(수급+실적)×기대감 등)은 단 1개도 변질·누락 없이 100% 유지**하되, 프롬프트 문장을 구조화하여 매 턴 베이스 토큰을 40% 경량화. |
| **⑤ 모델 세대교체 대응 유연성 부족** | 규칙서와 가이드에 특정 모델명이 고정되어 후속 모델(`Argon Flash`, `Gemini 5.0` 등) 출시 시 일괄 변경이 번거로움. | 유지보수 비효율 | **`model_config.json` 기반 2-Tier 모델 추상화 아키텍처**:<br>• **1순위 모델(`Tier-1 Flagship`: 현 `Gemini 4.0 Argon Medium`)**과 **2순위 모델(`Tier-2 High-Speed`: 현 `Gemini 3.8 Flash High`)**로 역할을 구조화하고, `model_config.json`에서 모델명만 바꾸면 전체 가이드·배지가 즉시 커스텀되도록 설계. |

---

## 🛠️ 2. 10대 사용자 요구사항 매핑 및 리프레이밍 설계안

1. **[요구사항 1 — 기존 기업 데이터 100% 존치]**:
   - `Stock_Research/` 내 개별 기업 폴더(14개 기업), 기존 작성된 `Phase1~3` 보고서, `Global_Trend/`, 개별 `Weekly_Trend/`, `portfolio_status.json`, `00_모바일_통합요약본.html`은 단 1바이트도 건드리지 않고 완벽히 보존합니다.
2. **[요구사항 2 — 신규 기업 폴더 및 HTML 생성 워크플로우 유지·고도화]**:
   - 신규 기업 폴더 생성 요청 시 `Stock_Research/[기업명]/` 하위 4대 폴더(`1_Raw_Data`, `2_Translated_DB`, `3_Final_Reports`, `Weekly_Trend`)와 6열 `thesis_log.md`, `company_timeline.md`가 생성되고, 분석 시 `Phase1~3.md` 및 `.html` 보고서가 생성되는 방식을 100% 동일하게 유지하되 `ksa_orchestrator.py`로 원샷 자동화합니다.
3. **[요구사항 3 — 기존 18대 핵심 분석 로직·목적 100% 무결성 보존]**:
   - `backtest_valuation.py`, `calc_reverse_dcf.py`, `generate_html.py`, `validate_report.py`, `s_curve_spec.md`에 축적된 모든 수리 공식(지배주주 분자, 희석/우선주/소급보정 분모, 업종 A~D 분기, SOTP 20% 룰, 4대 레짐, 사이클 피크 캡, Step 1.2 10% 변곡점·3축 병목·리드타임, Step 1.8 K-주주환원·분리과세·환원절벽·특수관계인 터널링, 레드팀 역산 Capa 천장, 안전핀 절대 부등식, 음수 FCF 오너정규화 폴백, 주가=(수급+실적)×기대감 4등급 테마 선별)을 100% 보존합니다.
4. **[요구사항 4 & 5 — Phase 1, 2, 3 작성 방식의 혁신적 효율화 (`One-Shot Prep ➔ Deep Reasoning ➔ One-Shot Build`)]**:
   - 보고서 구조(Phase 1 기업해독기 / Phase 2 스토리리더 / Phase 3 가격판독기)의 깊이 있는 장점은 그대로 살리되, **에이전트의 작업 프로토콜을 65회 도구 호출 ➔ 최대 4~6회 도구 호출 구조**로 전면 혁신합니다:
     - **[Step 1: `ksa_orchestrator.py prep` (도구 호출 1회)]**: SSOT 연산 + 역DCF + 2-Tier 스마트 PDF 원문 발췌 + 기존 가설 통합 브리핑 파일(`2_Translated_DB/ai_prep_digest.md`) 자동 생성.
     - **[Step 2: `read_file(".../ai_prep_digest.md")` (도구 호출 1회)]**: AI가 수십 개 파일을 뒤지는 대신, 단 1개의 통합 브리핑 문서만 읽고 모든 정량 테이블과 무손실 원문 발췌본을 한 번에 파악.
     - **[Step 3: 보고서 작성 또는 핀셋 패치 (도구 호출 1~3회)]**:
       - *Track A (신규 기업 / 정기 분기·반기·사업보고서)*: `Phase1_Report.md`, `Phase2_Story.md`, `Phase3_DCF.md`, `thesis_log.md` 심층 작성.
       - *Track B (격주 Global/Weekly Trend 점검)*: `thesis_log.md`, `company_timeline.md`(필요 시 `Phase2/3` 서사 문단)만 `edit_file`로 핀셋 갱신! (`Phase1/3`의 모든 주가·목표가·역DCF·SOP 매수가 표와 HTML 태그는 Step 4에서 코드가 자동 패치!)
     - **[Step 4: `ksa_orchestrator.py build --patch-ssot` (도구 호출 1회)]**: 코드 자동 생성 표/태그 자동 동기화 + HTML 3종 일괄 변환 + `validate_report.py` 무결성 통과 확인!
5. **[요구사항 6 & 7 — 보고서 퀄리티 1순위 & Gemini AI Pro 맞춤형 2-Tier 모델 커스텀 체계]**:
   - `korean-stock-analyzer/model_config.json`을 신설하여 **1순위 최상위 추론 모델(`Tier-1`: 기본값 `Gemini 4.0 Argon (Medium)`)**과 **2순위 고속 모델(`Tier-2`: 기본값 `Gemini 3.8 Flash High`)**을 정의하고, 향후 후속 모델(`Argon Flash`, `Gemini 5.0` 등) 발표 시 `python ksa_orchestrator.py set-models --tier1 "..." --tier2 "..."` 한 줄(또는 자연어 명령)로 전체 시스템과 `이용방법.html`이 즉시 업데이트되도록 구현합니다.
6. **[요구사항 8 — 모델별·상황별 완벽 정리된 `이용방법.html` 작성]**:
   - `e:\antigravity-work\my-skill\이용방법.md` 및 `이용방법.html`을 전면 리프레이밍하여 ① 1순위 모델 vs 2순위 모델 역할 분담 매트릭스, ② 후속 모델 발표 시 커스텀 방법, ③ 상황별(신규 폴더 생성 및 신규 기업 분석 / 분기·반기·사업보고서 업데이트 / Global Trend & Weekly Trend 반영 / 과거 데이터 `주가=(수급+실적)×기대감` 역추적 / 2-Step 극한 쿼터 절약 분업 / 모바일 요약본 동기화) 복사-붙여넣기 명령어와 예상 토큰 소모량을 직관적인 다크모드/인쇄최적화 HTML 대시보드 형태로 저장합니다.
7. **[요구사항 9 & 10 — 저토큰 정밀 테스트 검증 및 불필요 파일 클린업]**:
   - 리프레이밍 구현 후 파이썬 단위 테스트를 단 1~2회 호출로 검증하고, 혼동을 주는 구버전·임시 파일(`daily_prices.csv`, `periods_summary.csv`, `이용방법.pdf`, `update/`, `IR_to_MD_Guide.md`, `sync_docs.py`, `korean-stock-analyzer/.taskmaster/`)을 깔끔하게 삭제 정리합니다.

---

## 📅 3. 단계별 실행 로드맵 (Execution Checklist)

- [x] **Step 1**: 현황 진단 및 리프레이밍 마스터 플랜(`plan.md`) 수립 완료
- [x] **Step 2**: `model_config.json` 및 `ssot_common.py` 업그레이드 (모델 커스텀 설정 로더 추가) 완료
- [x] **Step 3**: `parse_pdf.py` v5.0 업그레이드 (2-Tier 키워드 스코어링 + 비관련 섹터 노이즈 필터 + 페이지 상한 캡으로 249쪽 폭발 원천 차단 & 100% 무손실 원문 유지) 완료
- [x] **Step 4**: `ksa_orchestrator.py` v5.0 신설 (`init`, `prep`, `build --patch-ssot`, `set-models` 4대 통합 명령어 및 `ai_prep_digest.md` 자동 생성기 구현) 완료
- [x] **Step 5**: `SKILL.md` 및 `GEMINI.md` v5.0 리프레이밍 (18대 무결성 원칙 100% 보존 + `One-Shot Prep & Build` 4~6턴 실행 규율 강제 + 프롬프트 경량화) 완료
- [x] **Step 6**: `이용방법.md`, `활용설명서.md`, `convert_guide.py` 리프레이밍 및 `이용방법.html` 생성 (1순위/2순위 모델별, 상황별 명령어 완벽 정리) 완료
- [x] **Step 7**: 최소 토큰 원샷 통합 테스트(18개 골든 테스트 통과 + 티씨케이 실전 검증) 및 불필요한 레거시 파일(`daily_prices.csv`, `periods_summary.csv`, `이용방법.pdf`, `update/`, `sync_docs.py`, `IR_to_MD_Guide.md`, `.taskmaster`) 클린업 완료
