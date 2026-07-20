---
name: hynix-report
description: SK하이닉스(000660) 국내 투자 리포트를 차트 포함 애널리스트 형식으로 작성해 reports/sk-hynix/에 저장한다. "하이닉스 리포트", "하이닉스 투자 리포트 만들어줘", "오늘 하이닉스 정리해줘" 같은 요청이나 정기 리포트 Routine에서 사용한다.
---

# SK하이닉스 투자 리포트 생성

SK하이닉스(KRX: 000660)의 주가·뉴스·산업 동향을 조사해 차트가 포함된 애널리스트 형식의 한국어 투자 리포트를 작성합니다.

## 절차

1. KST 기준 오늘 날짜를 확인합니다: `TZ=Asia/Seoul date +"%Y-%m-%d (%a)"`
2. **주가 데이터** — WebSearch(`"SK하이닉스" 주가 마감 YYYY-MM-DD`, "SK하이닉스 시가총액 PER")로 확인합니다: 최근 2주 일별 종가(등락률 보도로 역산 가능하면 역산치로 보충하되 표기), 52주 최고·최저, 시가총액, PER·PBR. (참고: finance.naver.com은 WebFetch가 차단되므로 WebSearch를 사용합니다.)
3. **전일 상세 시세(OHLCV)** — GitHub Actions `quote.yml`의 최근 성공 런에서 "Show quote" 스텝 로그를 읽습니다 (github MCP `actions_list`/`get_job_logs`). `days` 배열에 최근 2거래일의 시가/고가/저가/종가/거래량이 있습니다. 최근 런이 오래됐으면 `workflow_dispatch`로 한 번 실행 후 로그를 읽습니다. (이 세션 환경에서는 야후·github.io 접근이 차단되어 `scripts/fetch_quote.py` 직접 실행은 불가.) 실패 시 WebSearch로 보충하고, 못 채운 칸은 "확인 불가"로 둡니다. 거래대금은 근사치(거래량×평균가)로 쓰지 말고 확인된 값만 적습니다.
4. **뉴스·공시** — WebSearch로 최근 1주일 내 주요 뉴스와 DART 공시를 조사합니다 (실적, 수주, 투자, HBM/DRAM/NAND 관련). 주가 영향력이 큰 순서로 **Top 5**를 선정합니다 (실적·수급·업황 관련 > 단순 홍보성 기사).
5. **실적** — 최근 3~4개 분기 확정 실적(매출·영업이익·이익률)과 다음 분기 컨센서스를 확인합니다.
6. **산업 동향** — DRAM/NAND/HBM 가격 추이, HBM 점유율(SK하이닉스·삼성전자·마이크론), 차세대 제품(HBM4 등) 일정을 조사합니다.
7. **증권사 의견** — WebSearch("SK하이닉스 목표주가")로 최근 증권사별 투자의견·목표주가와 컨센서스를 수집합니다.
8. **차트 생성** — 조사한 수치로 `reports/sk-hynix/assets/YYYY-MM-DD/data.json`을 작성합니다 (형식은 기존 날짜 폴더의 data.json 참고). 라이트/다크 두 세트를 생성합니다:
   ```
   python3 scripts/hynix_charts.py reports/sk-hynix/assets/YYYY-MM-DD/data.json reports/sk-hynix/assets/YYYY-MM-DD
   python3 scripts/hynix_charts.py reports/sk-hynix/assets/YYYY-MM-DD/data.json reports/sk-hynix/assets/YYYY-MM-DD/dark --dark
   ```
   price_trend / target_prices / quarterly_earnings / hbm_share 4개 SVG가 세트별로 생성됩니다. 라이트는 마크다운 리포트용, 다크는 웹 페이지(latest.html)용입니다. 확보 못 한 데이터의 차트는 data.json에서 해당 키를 빼면 생성이 생략됩니다.
   (참고: 뉴스 앵커 기반 `three_month_trend`는 2026-07-16에 폐기 — 앵커 사이 선형 보간이 6월 말 고점(~298만) 구간을 누락하는 문제. 3개월 추세는 quote 워크플로의 야후 실데이터 일봉 캔들차트(`docs/charts/candle_volume.svg`)가 담당합니다.)
9. `reports/sk-hynix/`의 가장 최근 리포트를 읽어 직전 대비 변화(투자 판단 변경 포함)를 파악합니다.
10. 아래 형식으로 리포트를 작성해 `reports/sk-hynix/YYYY-MM-DD.md`로 저장합니다.
11. **웹 페이지 빌드·발행** — `scripts/report_template.html`을 오늘 리포트 내용으로 갱신한 뒤(구조·CSS·다크 테마·툴바·`__차트마커__`는 유지, 텍스트만 교체) 빌드합니다:
    ```
    python3 scripts/build_web.py YYYY-MM-DD
    ```
    - `reports/sk-hynix/latest.html` (Artifact용, TradingView 위젯 제외) → Artifact 도구로 **같은 파일 경로**를 재발행하면 고정 URL이 유지됩니다.
    - `docs/index.html` (GitHub Pages용, TradingView 실시간 시세 위젯 포함) → 커밋·푸시하면 `.github/workflows/pages.yml`이 자동 배포합니다. Pages URL: https://godajava.github.io/sk-hynix-investment-report/
    - 고정 URL: https://claude.ai/code/artifact/e9f34125-bb5e-4888-8185-3fc8e3d343fa (다른 세션에서 발행할 때는 이 URL을 Artifact의 `url` 파라미터로 전달)
    - favicon은 📊로 고정, label은 당일 날짜(YYYY-MM-DD)로 지정합니다.
12. 저장 경로, 아티팩트 URL, 핵심 요약(뉴스 Top 5, 투자 판단 포함)을 사용자에게 보고합니다.

## 리포트 형식 (애널리스트 스타일)

전체 예시는 `reports/sk-hynix/2026-07-15.md`를 참고하세요. 골격:

```markdown
# SK하이닉스 (000660.KS)
## <리포트 헤드라인 한 줄 — 그날의 핵심 논지>
**Company Report | 반도체/메모리 | YYYY-MM-DD**

| 투자의견 | 현재가 | 컨센서스 목표주가 | 상승여력 | 차기 촉매 |
(5칸 헤더 테이블 — 한눈 요약)

> 작성 시점 + 면책 한 줄

## 1. 투자 요약 (Investment Summary)   ← 불릿 3~4개 + 핵심 지표 테이블
## 2. 주가 동향                        ← three_month_trend.svg + price_trend.svg + 전일 상세 시세 표(시가/고가/저가/종가/등락/거래량) + 해설 + 일별 종가 표
## 3. 최신 뉴스 Top 5                  ← 중요도순, 각 항목 🟢호재/🔴악재/⚪중립 태그 + 출처 링크
## 4. 실적 분석                        ← quarterly_earnings.svg + 해설
## 5. 산업 동향 — HBM·NAND            ← hbm_share.svg + HBM/DRAM 불릿(가격/수요/경쟁/차세대) + NAND 불릿(시장 규모·eSSD 수요·가격 전망·점유율)
## 6. 밸류에이션 — 증권사 목표주가      ← target_prices.svg + 강세론/신중론 대비
## 7. Bull vs Bear                     ← 2열 테이블 (투자 포인트 vs 리스크 요인)
## 8. 투자 판단                        ← **매수/중립/매도** + 근거 1~3(뉴스·섹션 인용) + 판단을 바꿀 조건

*면책 문구*
```

차트 삽입은 상대 경로를 사용합니다: `![설명](assets/YYYY-MM-DD/price_trend.svg)`

## 규칙

- 확인하지 못한 수치는 지어내지 말고 "확인 불가"로 표기합니다. 등락률 보도로 역산한 값은 역산치임을 차트와 표에 표기합니다.
- 주요 수치·인용에는 출처(언론사·증권사·DART)를 밝힙니다.
- 차트는 반드시 `scripts/hynix_charts.py`로 생성합니다 (팔레트·마크 규격이 dataviz 검증을 통과한 상태로 고정되어 있음). 스크립트 색상·스타일을 임의 변경하지 않습니다.
- 같은 날짜 리포트가 이미 있으면 덮어쓰지 말고 내용을 갱신(수정)하고, 갱신 사실을 보고합니다.
- 투자 판단(매수/중립/매도)은 애널리스트 의견으로서 반드시 근거·판단 변경 조건과 함께 제시하고, 근거 없이 단정하지 않습니다. 면책 문구는 반드시 포함합니다.
