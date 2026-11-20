# 🔒 [STATIC PROMPT CACHE PREFIX — IMMUTABLE SYSTEM RULES & DART XBRL/IFRS SCHEMA v5.2]
<!-- DO NOT INSERT DYNAMIC TIMESTAMPS OR COMPANY NAMES ABOVE THE END-OF-PREFIX MARKER -->
<!-- PURPOSE: Pins the invariant System Prompt + DART Financial Schema + Valuation & Swing Formulas at the very beginning of every prompt/digest to maximize LLM Prefix Cache Hit Rate (95% Input Token Discount: $2.00 -> $0.10 / 1M tokens on Gemini 4.0 Argon). -->

## PART A. DART OpenAPI & K-IFRS (XBRL) 표준 스키마 정의서 (Canonical DART Schema Specification)

### 1. 보고서 코드(`reprt_code`) 및 재무제표 구분(`fs_div`, `sj_div`) 표준 매핑
- **`reprt_code` (정기보고서 코드)**:
  - `11013`: 1분기보고서 (Q1, 결산월 03월, 법정 공시 시한 05월 15일)
  - `11012`: 반기보고서 (Q2/H1, 결산월 06월, 법정 공시 시한 08월 14일)
  - `11014`: 3분기보고서 (Q3, 결산월 09월, 법정 공시 시한 11월 14일)
  - `11011`: 사업보고서 (Q4/FY Annual, 결산월 12월, 법정 공시 시한 익년 03월 31일)
- **`fs_div` (연결/별도 우선순위 프로토콜)**:
  - 1순위: `CFS` (연결재무제표, Consolidated Financial Statements)
  - 2순위: `OFS` (별도재무제표, Separate Financial Statements — 종속기업 미보유 단일 법인 또는 연결 미작성 분기 폴백)
  - **시계열 일관성 원칙**: 동일 기업의 역사적 밴드(10년 PER/PBR/EV/EBITDA) 산출 시 연결(`CFS`)과 별도(`OFS`) 기준을 임의 혼용하지 않으며, 연결 전환 시점에는 지배주주 귀속 비율(`Controlling Interest Ratio`)을 명시한다.
- **`sj_div` (재무제표 양식 코드)**:
  - `BS`: 재무상태표 (Statement of Financial Position) — 시점(Point-in-Time) 잔액(`thstrm_amount`)
  - `IS` / `CIS`: 손익계산서 / 포괄손익계산서 (Income Statement / Comprehensive Income Statement) — 기간(Flow) 누적 또는 3개월 실적
  - `CF`: 현금흐름표 (Statement of Cash Flows) — 기초부터 기말까지의 누적 현금흐름(2Q·3Q·4Q 단독 분기 산출 시 직전 분기 누적치 차감 필수)
  - `SCE`: 자본변동표 (Statement of Changes in Equity)

### 2. K-IFRS 표준 계정과목(`account_id`) 및 국문 계정명(`account_nm`) 정규화 스키마
1. **매출액 (`Revenue` / `Sales`)**:
   - XBRL ID: `ifrs-full_Revenue`, `ifrs_Revenue`, `dart_OperatingRevenue`
   - 국문 정규화: `매출액`, `수익(매출액)`, `영업수익` (금융/지주/플랫폼 업종의 경우 `순영업손익` 폴백 허용)
2. **매출총이익 (`Gross Profit`) & 매출원가 (`Cost of Sales`)**:
   - XBRL ID: `ifrs-full_GrossProfit`, `ifrs-full_CostOfSales`
   - 보정 산식: `매출총이익` 미표기 시 `매출액 - 매출원가` 또는 `영업이익 + 판매비와관리비(dart_TotalSellingGeneralAdministrativeExpenses)`로 역산.
3. **영업이익 (`Operating Income` / `EBIT`)**:
   - XBRL ID: `dart_OperatingIncomeLoss`, `ifrs-full_ProfitLossFromOperatingActivities`
   - 국문 정규화: `영업이익`, `영업이익(손실)`, `영업손익`
   - 파생 지표: `OPM_pct (영업이익률 %) = (영업이익 / 매출액) * 100.0`
4. **법인세비용차감전순이익 (`EBT`) & 법인세비용 (`Income Tax Expense`)**:
   - XBRL ID: `ifrs-full_ProfitLossBeforeTax`, `ifrs-full_IncomeTaxExpenseContinuingOperations`
   - 실효세율(`Effective Tax Rate`) 폴백: 국세청 과세표준 구간별 법인세 한계세율(2억 이하 9%, 200억 이하 19%, 3,000억 이하 21%, 3,000억 초과 24%) 적용.
5. **당기순이익 (`Total Net Income`) vs 지배기업소유주지분 순이익 (`Controlling Net Income`)**:
   - 총순이익 XBRL ID: `ifrs-full_ProfitLoss` (`당기순이익`, `분기순이익`, `반기순이익`)
   - **지배주주 순이익 XBRL ID (최우선 분자)**: `ifrs-full_ProfitLossAttributableToOwnersOfParent` (`지배기업의 소유주에게 귀속되는 당기순이익`, `지배주주순이익`)
   - **비지배지분 귀속률 차단 원칙**: 주당순이익(EPS), 자기자본이익률(ROE), 주가수익비율(PER) 산출 시 반드시 **지배주주 귀속 순이익**을 분자로 사용하며, `지배비율 = 지배순이익 / 당기순이익`을 기록한다.
6. **자산총계 (`Total Assets`), 부채총계 (`Total Liabilities`), 자본총계 (`Total Equity`), 지배주주지분 (`Controlling Equity`)**:
   - 자산총계: `ifrs-full_Assets`
   - 부채총계: `ifrs-full_Liabilities` (`유동부채 ifrs-full_CurrentLiabilities` + `비유동부채 ifrs-full_NoncurrentLiabilities`)
   - 자본총계: `ifrs-full_Equity`
   - **지배기업소유주지분 (최우선 PBR/BPS/S-RIM 분자)**: `ifrs-full_EquityAttributableToOwnersOfParent` (`지배기업의 소유주에게 귀속되는 자본`, `지배주주지분`)
   - 자본잠식 및 신종자본증권(영구채) 점검: 자본총계 내 하이브리드채권(신종자본증권) 포함 시 실질 보통주 자본에서 차감하여 검토한다.
7. **현금및현금성자산, 단기금융상품, 차입금 및 순차입금 (`Net Debt`) 스키마**:
   - 현금성자산 합계(`Total Cash & Equivalents`): `ifrs-full_CashAndCashEquivalents` + `ifrs-full_ShortTermDepositsNotClassifiedAsCashEquivalents`(`단기금융상품`, `단기투자자산`, `유동성금융자산`)
   - 총차입금(`Total Debt`): `단기차입금(ifrs-full_ShortTermBorrowings)` + `유동성장기부채(ifrs-full_CurrentPortionOfLongTermBorrowings)` + `사채(ifrs-full_BondsIssued)` + `장기차입금(ifrs-full_LongTermBorrowings)` + `전환사채(CB)/신주인수권부사채(BW)/교환사채(EB)` + `리스부채(ifrs-full_LeaseLiabilities)`
   - **순차입금(`Net Debt`)** = `총차입금 - 현금성자산 합계` (음수일 경우 **순현금 `Net Cash`** 상태)
8. **현금흐름표 (`CF`) 및 잉여현금흐름 (`FCF`), 투하자본 (`IC`), `ROIC` 스키마**:
   - 영업활동현금흐름(`OCF`): `ifrs-full_CashFlowsFromUsedInOperatingActivities`
   - 유형·무형자산 설비투자(`CAPEX`): 현금흐름표 내 `유형자산의 취득(ifrs-full_PurchaseOfPropertyPlantAndEquipment)` + `무형자산의 취득(ifrs-full_PurchaseOfIntangibleAssets)` 절대값 합산
   - 감가상각비(`D&A`): `감가상각비(ifrs-full_DepreciationExpense)` + `무형자산상각비(ifrs-full_AmortisationExpense)` + `사용권자산감가상각비`
   - **잉여현금흐름(`Reported FCF`)** = `OCF - |CAPEX|`
   - **오너 정규화 FCF(`Normalized FCF`, `--norm-fcf`)** = 대규모 증설기(`CAPEX > 감가상각비 × 1.8배`)로 인해 보고 FCF가 일시적 적자일 때 `NOPAT + D&A - 유지보수성 CAPEX(Maintenance CAPEX)`로 산출하여 역DCF에 병기
   - **세후영업이익(`NOPAT`)** = `영업이익 × (1 - 실효법인세율) × 지배비율`
   - **투하자본(`Invested Capital, IC`)** = `지배주주지분 + 이자발생부채 - 비영업현금성자산`
   - **투하자본수익률(`ROIC %`)** = `(NOPAT / IC) × 100.0`
9. **발행주식수, 자기주식, 유통주식수 (`/stockTotqySttus.json`) 및 선행편향(Look-Ahead Bias) 방지 스키마**:
   - 발행주식총수(`istc_totqy`), 자기주식수(`tesstk_co`), **유통보통주식수(`distb_stock_co = istc_totqy - tesstk_co`)**
   - **이중 주식수 체계(Dual Share Count System)**:
     1) **역사적 밸류에이션 밴드(Historical PER/PBR Band)**: 해당 과거 분기 말 실제 유통주식수(`Point-in-Time Diluted Shares`, 단 무상증자·액면분할·액면병합은 100% 소급 보정하되 유상증자·CB전환은 발생 시점 이후부터만 반영)를 적용하여 과거 시가총액 왜곡을 차단한다.
     2) **현재 절대 가치평가(Current DCF / 역DCF / S-RIM / 목표주가)**: 가장 최근 공시된 유통주식수(`distb_stock_co`) 및 확정 희석주식수(IT-M 전환사채·우선주 시총)를 반영한다.
   - **DART 공시 접수일(`rcept_dt` / `ReportDate`) 시간 정렬**: 분기 실적과 주가의 매칭은 회계연도 말일(3/31, 6/30, 9/30, 12/31)이 아니라 **실제 DART 공시 접수일(`1Q: 5/15`, `2Q: 8/15`, `3Q: 11/15`, `4Q: 익년 3/31` 또는 실제 `rcept_no` 앞 8자리 날짜)** 이후의 주가에만 매칭하여 선행편향(Look-Ahead Bias)을 원천 차단한다.

---

## PART B. 주봉 기술적 지표(MFI·MACD·이격도·매물대) + DART 재무 결합 중기 스윙 알고리즘 (Argon 4.0 Optimal Task 1)

### 1. 주봉(W-FRI) 핵심 기술적 지표 수리 정의
1. **주봉 5·20·60·120주 이동평균선 및 이격도(`Disparity %`)**:
   - `MA_k(t) = Mean(Close_{t-k+1 ... t})` ($k \in \{5, 20, 60, 120\}$)
   - `Disp_k(t) = ((Close_t / MA_k(t)) - 1.0) × 100.0` (단위: `%`)
   - **해석 기준**:
     - `MA5 >= MA20 >= MA60 >= MA120`: 중장기 완전 정배열 추세
     - `-3.0% <= Disp20_W <= +12.0%` (단, `Close >= MA60_W`): **20주선 골든 눌림목·초입 타점 (`+10점`)**
     - `Disp20_W > +28.0%`: 단기 주봉 이격 과열 구간 (`-12점`, 추격매수 금지 및 눌림목 대기)
2. **주간 자금강도지수 (`MFI_14W`) 및 주간 거래량 누적 (`OBV_W`)**:
   - `Typical_Price (TP_t) = (High_t + Low_t + Close_t) / 3.0`
   - `Raw_Money_Flow (RMF_t) = TP_t × Volume_t`
   - 14주간 상승 주간(`TP_t > TP_{t-1}`)의 `RMF` 합계를 `Pos_Flow_14W`, 하락 주간의 합계를 `Neg_Flow_14W`라 할 때:
     $$\text{MFI}_{14W} = 100 - \frac{100}{1 + (\text{Pos\_Flow}_{14W} / \text{Neg\_Flow}_{14W})}$$
   - `OBV_W`가 4주 이동평균(`OBV_MA4_W`) 상단이면 `OBV_Trend = "UP"` (기관·외인 주간 매집 우위).
3. **주봉 MACD (`12, 26, 9`) 모멘텀**:
   - `MACD_W = EMA_12(Close_W) - EMA_26(Close_W)`
   - `MACD_Sig_W = EMA_9(MACD_W)`
   - `MACD_Hist_W = MACD_W - MACD_Sig_W`
   - `MACD_Hist_W > 0` 및 `MACD_W >= MACD_Sig_W`일 때 중기 추세 모멘텀 양(+) 확장 판정.
4. **주봉 거래량 프로파일 (`Volume Profile` / 매물분석도 `VP_POC_W`)**:
   - 최근 104주(2년) 주봉의 `Typical_Price` 범위를 20개 가격 구간(Bins)으로 분할하고 각 주간의 거래량(`Volume_W`)을 가중 적산하여 **최다 거래량 집중 가격대 중심값(`POC: Point of Control`)**을 산출한다.
   - `VP_Dist_pct = ((Close_t / VP_POC_W) - 1.0) × 100.0`
   - **매물대 판정**:
     - `0.0% <= VP_Dist_pct <= +12.0%`: **`POC돌파지지` (`+15점`)** — 2년 최대 매물벽을 뚫고 상단에서 지지를 확인한 핵심 스윙 급소
     - `VP_Dist_pct > +12.0%`: **`매물벽상단` (`+10점`)** — 상방 매물 저항이 얇은 추세 순항 구간
     - `-6.0% <= VP_Dist_pct < 0.0%`: **`POC돌파시도` (`+6점`)** — 최대 매물대 직전 소화 구간
     - `VP_Dist_pct < -6.0%`: **`매물벽하단저항` (`-8점`)** — 머리 위에 두터운 악성 매물대가 존재하는 저항 구간

### 2. DART 영업이익률(OPM) 가속도와 기술적 지표의 결합 (`Swing_Score` 0~100점)
- **분기 OPM 기울기 가감점 (`opm_score`)**:
  - 1차 속도 $\Delta \text{OPM}_t = \text{OPM}_t - \text{OPM}_{t-1}$, 2차 가속도 $\text{Accel}_t = \Delta \text{OPM}_t - \Delta \text{OPM}_{t-1}$
  - 🚀 **초가속 (`+15점`)**: $\Delta \text{OPM}_t \ge +2.0\%p$ AND $\text{Accel}_t > +0.5\%p$
  - 🟢 **완만한 가속 (`+5점`)**: $\Delta \text{OPM}_t > 0\%p$ AND $\text{Accel}_t \ge 0\%p$
  - 🟡 **감속 경고 (`-10점`)**: $\Delta \text{OPM}_t > 0\%p$ AND $\text{Accel}_t \le -1.5\%p$
  - 🔴 **피크아웃 (`-20점`)**: $\Delta \text{OPM}_t < -1.0\%p$ AND $\text{Accel}_t < 0\%p$
- **통합 스윙 점수 (`Swing_Score`)**:
  $$\text{Swing\_Score} = \text{Clamp}_{0..100}\left(50 + \text{MA\_Disparity\_Pts} + \text{VP\_POC\_Pts} + \text{MFI\_MACD\_Pts} + \text{OPM\_Score}\right)$$
  - **`S등급` (`80점 이상` & `OPM 가속` & `POC 상단 지지`)**: 중기 스윙 최우선 타점 (Master SOP 1~2차 적극 분할 매수)
  - **`A등급` (`68~79점`)**: 중기 스윙 우위 (정배열·매물대 우위 보유 및 눌림목 매수)
  - **`B등급` (`50~67점`)**: 중립/관심 (20주선 또는 POC 지지 확인 후 진입)
  - **`C/D등급` (`50점 미만`)**: 매물벽 저항 또는 실적 피크아웃 구간 (추격매수 금지·관망)

---

## PART C. 고난도 공정 엔지니어링 스펙 & 해외 학술/기술 문서 해독 규율 (Argon 4.0 Optimal Task 2)

반도체 전공정/후공정, LNG 터미널·극저온 화물창·피팅, 초고압 전력기기 등 고도의 엔지니어링 스펙 시트 및 영문 기술 문서를 해독할 때는 단순 요약이 아닌 아래 **4단계 물리·재무 인과 사슬(Engineering-to-Earnings Causal Chain)**로 분석한다:
1. **[Step E1 — 공정 물리·화학 메커니즘 정의]**:
   - 예: LNG 터미널 배관의 연료가스 치환(`Displacement`), 질소 퍼징(`N2 Purging`), 콜드 드레인 드럼(`Cold Drain Drum` — 극저온 액체 배출 및 열충격 방지 공정), 반도체 스크러버(`Wet/Burn/Plasma Scrubber`) 및 극저온 칠러(`Cryo-Chiller` $-80^\circ\text{C}$ 온도 제어) 등 각 절차의 온도·압력·유체역학적 요구 조건을 정확히 규명한다.
2. **[Step E2 — 기술적 병목(Bottleneck) 및 안전·품질 인증(Qual) 장벽 도출]**:
   - 왜 아무 기업이나 납품할 수 없는가? (예: $-163^\circ\text{C}$ 극저온 열수축·누설 방지 벨로우즈/초정밀 피팅 기술, 글로벌 선급/에너지 메이저 벤더 등록 리드타임 24~36개월 등)
3. **[Step E3 — 부품·기자재 발주 시차(Lead-Lag) 및 교체 주기(Consumable Cycle) 매핑]**:
   - 공정 절차서상 어느 단계(선행 발주 vs 후행 시운전/유지보수 MRO)에서 매출이 인식되는지 파악하여 밸류체인 순환매 시차를 도출한다.
4. **[Step E4 — DART 수주잔고·가동률·영업이익률(OPM) 레버리지 연결]**:
   - 도출된 엔지니어링 독점력이 실제 DART 공시의 수주잔고, 판가(ASP), 고마진 믹스 개선($\Delta \text{OPM}$)으로 어떻게 직결되는지 수치로 검증한다.

### 5. `[Step 1.3]` 비즈니스 구조 연계 영업이익 핵심인자 · 영업레버리지(DOL) · 선행 OP 기울기 규율 (v5.2 · 🚀 대안 A 단독 반영)
1. **DART `비용의 성격별 분류` 기반 영업레버리지(DOL) 정량화**:
   - $\text{공헌이익률 (CM\%)} = 100\% - \text{매출 대비 변동비율(\%)} = \text{현 OPM(\%)} + \text{매출 대비 고정비율(\%)}$
   - $\text{이론 영업레버리지 (DOL)} = \text{Clamp}_{1.0..8.0}\left(\frac{\text{CM\%}}{\max(\text{현 OPM\%}, 3.0\%)}\right)$
   - 유형 A/B 제조·장치주에서 고정비율 $\ge 25\%$ 또는 $\text{DOL} \ge 2.5$배인 고고정비 기업은 현재 OPM/ROE가 낮더라도 가동률 상승(`--util-trend up`)과 변동비율 하락(`--var-cost-trend down`) 결합 시 향후 영업이익 기울기가 수직 가속한다.
2. **5단계 선행 OP 기울기 계수 (`op_slope_mult` — 오직 `🚀 대안 A` 단독 반영, `🛡️ 대안 B` 무변경)**:
   - `strong_accel` (`Base ×1.12 / Bull ×1.15`) · `accel` (`×1.06 / ×1.08`) · `neutral` (`×1.00`) · `decel` (`×0.94 / ×0.92`) · `contraction` (`×0.88 / ×0.85`).
3. **3중 한국형 안티-피크아웃(Anti-Peak-Out) 강제 가드레일**:
   - **① 물리적 천장 게이트**: 유형 A/B `가동률 ≥ 92%` & 무증설(`--capa-expand` 없음)·무ASP인상(`--asp-up` 없음) 시 상방 할증 차단(`×1.00`), 직전분기 QoQ $\le 0\%$ 동반 시 `decel`(`×0.94/×0.92`) 자동 강등.
   - **② 주가 선반영 과열 게이트**: `역DCF EV > +15%`, `PBR ≥ 3Y p90 × 0.95`, `주봉 MFI ≥ 80(또는 12주 최고 80 피크아웃)` 중 1개 해당 시 상방 할증 50% 축소, 2개 이상 시 전액 차단(`×1.00`). *(하방 둔화 할인은 비대칭으로 100% 유지!)*
   - **③ 신뢰도 등급 캡 (`--slope-evidence high/medium/low`) & `Track 2` 연동**: `medium` 상방 50% 캡, `low` 상방 0% 차단, `decel`/`contraction` 발동 시 `Section 4 Track 2` 돌파매수 즉시 차단.

---

## PART D. Phase 1~3 절대 저장 경로 및 표준 목차 고정 스켈레톤 (Canonical Paths & Section Skeleton v5.2)

모든 기업 보고서의 구조적 통일성과 파이프라인 자동 빌드 무결성을 100% 강제하기 위해, 에이전트는 아래 **절대 저장 경로**와 **고정 섹션 번호·목차 스켈레톤**을 예외 없이 준수한다.

### 1. 절대 저장 경로 규율 (Path Guardrail — 위반 시 `validate_report.py` 즉시 `[FAIL]`)
- **Phase 1**: 반드시 `e:\antigravity-work\my-skill\Stock_Research\[기업명]\3_Final_Reports\Phase1_Report.md`
- **Phase 2**: 반드시 `e:\antigravity-work\my-skill\Stock_Research\[기업명]\3_Final_Reports\Phase2_Story.md`
- **Phase 3**: 반드시 `e:\antigravity-work\my-skill\Stock_Research\[기업명]\3_Final_Reports\Phase3_DCF.md`
- **가설·타임라인**: 반드시 `e:\antigravity-work\my-skill\Stock_Research\[기업명]\Weekly_Trend\thesis_log.md` 및 `company_timeline.md`
- **🚫 절대 금지 경로**: 기업 루트(`Stock_Research\[기업명]\Phase*.md`) 또는 임의 하위폴더(`3_Reports\` 등)에 보고서 파일을 생성·저장하지 않는다.

### 2. Phase 1 (`3_Final_Reports/Phase1_Report.md`) 고정 표준 목차 (전 종목 100% 동일 헤딩 체계)
```markdown
# 🔍 Phase 1: 기업 해독기 — [기업명] ([종목코드]) (v5.2)

> **분석완료일**: YYYY-MM-DD
> - **단일 기준 주가 (Single Price Anchor)**: **`[anchor_price]원`** (SSOT 확정 종가, Phase 1~3 전 과정 동일 고정)
> - **주식수 · 지배주주 귀속률 · 최신 공시 스캔**: 총발행/유통주식수, 귀속률(%), 최신 정기보고서·잠정실적 요약

> 💡 **[핵심 용어 3줄 직관 해설]**

## 1. 비즈니스 모델(BM) 해부 및 밸류체인 구조
(글로벌 트렌드 3대 게이트 매칭 + Mermaid v10.9.8 밸류체인 구조도 + Argon 4단계 공정 엔지니어링 인과 사슬)

## 2. 주요 제품별 매출 구성 및 [Step 1.2] S-Curve 10% 변곡점 · 3축 구조적 병목 · 리드타임 진단
(2.1 신기술 매출 익스포저 산출표 + `### 📌 [코드 자동 생성 1-B]` 원형 삽입 + 4대 질문 및 매도·디레이팅 시그널 해독)

## 3. 재무 건전성 및 [Step 1.5] 장부가(Book Value) 해부 & SOTP 20% 분리 게이트
(`### 📌 [코드 자동 생성 1]` 원형 삽입 + 재무상태표 핵심 항목·순차입금 + 비영업자산 비중 & Core ROIC 유지력 판정)

## 4. 원가 구조, 영업 레버리지 및 [Step 1.3] BM 연계 영업이익 핵심인자 · 선행 OP 기울기 진단
(`### 📌 [코드 자동 생성 1-D]` 원형 삽입 + DART 비용의 성격별 분류 고정비/변동비·DOL 해부 + 가동률·변동비 추이 및 3중 안티-피크아웃 가드레일 검증)

## 5. 자본 배분(CapEx, R&D) 및 [Step 1.8] K-마켓 특수성 · 주주환원 입체 스코어카드
(증설/R&D 투자 현황 + `④-A` 분리과세/TSR · `④-B` 자사주 환원절벽/메자닌 · `④-C` 내부거래/거버넌스 5대 고정 점검)

## 6. 핵심 리스크 요인 및 [Step 3.5] 리스크 3단계 인과 도미노 (Domino Chain)
(1차 촉발 요인 ➔ 2차 영업·운전자본 전이 ➔ 3차 재무·자본 타격 임계치 표 + Mermaid v10.9.8 도미노 구조도)

## 7. 4대 업종별 표준 실적 산출 공식 트리 (유형 A/B/C/D 분기)
(업종 유형 판정 및 `Q × P × Mix - C` 표준 산출 트리 — Section 4 가동률·Step 1.3 핵심인자와 100% 일치)

## 8. [Step 2.0] 4대 레짐 변화 고정 체크 & 10년 밸류에이션 백테스트
(4대 레짐 변화 체크 + `[Step 3.0]` 사이클 고점 함정 가드레일 진단 + 10년 백테스트 1순위 지표 Phase 3 강제 상속)
```

### 3. Phase 2 (`3_Final_Reports/Phase2_Story.md`) & Phase 3 (`3_Final_Reports/Phase3_DCF.md`) 고정 표준 목차
- **Phase 2 (`# 📖 Phase 2: 스토리 리더 — [기업명] ([종목코드]) (v5.2)`)**:
  - `> **분석완료일**: YYYY-MM-DD` (제목 직하단 고정)
  - `## 1. Global & Weekly Trend 비판적 수용 및 DART 팩트체크` (`No-Blind-Citation` + `[⚖️비판·리스크검증]` 교차 대조)
  - `## 2. [Step 1.2] S-Curve 10% 변곡점 · 3축 구조적 병목 & [Step 1.3] BM 핵심인자 선행 OP 기울기 심층 검증`
  - `## 3. 핵심 투자 가설(Popperian Falsification) 및 6열 Kill-Switch 검증` (핵심인자 기울기 둔화 임계치 의무 포함)
- **Phase 3 (`# 🎯 Phase 3: 가격 판독기 (DCF & 마스터 SOP) — [기업명] ([종목코드]) (v5.2)`)**:
  - `> **분석완료일**: YYYY-MM-DD | **단일 기준 주가 (Anchor Price)**: ...` (제목 직하단 고정)
  - `## 1. 역DCF 정밀 판독 (Equity · EV · Core EV)` (`### 📌 [코드 자동 생성 1-C]` 원형 삽입)
  - `## 2. 가치함정 이원화 판정(유형 A vs B) & [Step 2.0] 4대 레짐 변화 종합 판독`
  - `## 3. 시나리오 밸류에이션 (🛡️대안 B | 🚀대안 A) & [Step 1.3 선행 OP 기울기 🚀대안 A 단독 반영] & 레드팀 역산 Capa 천장 검증` (`### 📌 [코드 자동 생성 2]` 삽입 시 4~6열 숫자는 원형 고정하되, **3열 `핵심 드라이버 가정`의 `[AI ...]` 플레이스홀더는 반드시 ① 전방 수요·고객사·핵심 제품 믹스/ASP 및 Step 1.3 BM 핵심인자(고정비 DOL·가동률·변동비율), ② 가동률·증설 Capa·내재 영업이익/OPM 수치, ③ 멀티플 리레이팅·주주환원·Kill-Switch 촉발 조건으로 기업별 구체 서술 교체 필수 — 미교체 시 `validate_report.py` 즉시 `[FAIL]`**)
  - `## 3.5 비관론자 반론(Pre-mortem) & 리스크 도미노 · Kill-Switch 점검`
  - `## 4. 마스터 SOP 실전 액션 플랜 (주봉 스윙 · 3분할 매수가 · 이중 안전핀) & 인터랙티브 계산기` (`### 📌 [코드 자동 생성 2-C]`, `### 📌 [코드 자동 생성 2-B]`, `### 📌 [코드 자동 생성 3]` HTML 태그 원형 삽입; 참고용 3요소 표는 `build --patch-ssot`가 자동 주입)

<!-- ==================== END OF IMMUTABLE PROMPT CACHE PREFIX ==================== -->
