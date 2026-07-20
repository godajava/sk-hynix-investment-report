# SK하이닉스 투자 리포트 에이전트

SK하이닉스(KRX **000660**) 국내 투자 리포트를 매 거래일 자동 생성·발행하는 에이전트입니다.
주가·뉴스·업황(메모리/HBM/NAND)·기술적 지표를 조사해 애널리스트 형식의 한국어 리포트를 만들고,
차트를 생성해 GitHub Pages로 발행합니다.

> ⚠️ 본 저장소의 리포트는 공개 보도·자료를 종합한 **정보 제공 목적**이며 투자 권유가 아닙니다.
> 투자 판단과 책임은 투자자 본인에게 있습니다.

## 라이브

- **웹 리포트 (GitHub Pages)**: https://godajava.github.io/sk-hynix-investment-report/
- **리포트 아카이브**: [`reports/sk-hynix/`](reports/sk-hynix)

## 구성

| 경로 | 설명 |
|---|---|
| `.claude/agents/sk-hynix-analyst.md` | 리포트 애널리스트 에이전트 정의 |
| `.claude/skills/hynix-report/SKILL.md` | 리포트 생성 12단계 절차 스킬 |
| `scripts/fetch_quote.py` | 야후 파이낸스 시세 수집 + 기술적 지표(MACD·ATR·ADX·KDJ 등) 계산 |
| `scripts/hynix_charts.py` | 가격·목표주가·실적·HBM 점유율 차트(SVG, 라이트/다크) 생성 |
| `scripts/tech_charts.py` | 캔들·거래량·MACD·KDJ·ADX/ATR 기술적 차트(다크 SVG) 생성 |
| `scripts/build_web.py` | 웹 페이지 빌드 (`docs/index.html`, `reports/sk-hynix/latest.html`) |
| `scripts/report_template.html` | 다크 테마 웹 리포트 템플릿 |
| `reports/sk-hynix/` | 일자별 리포트(MD)·차트 assets |
| `docs/` | GitHub Pages 사이트 (index.html, quote.json, charts) |
| `.github/workflows/` | 시세 갱신(quote)·차트 커밋(charts)·Pages 배포(pages) 자동화 |

## 자동화 워크플로

| 워크플로 | 트리거 | 역할 |
|---|---|---|
| `quote.yml` | 장중 10분마다(평일 KST 09~15시) | 시세·기술 차트 갱신 후 Pages 배포 |
| `charts.yml` | 평일 16:10 KST | 확정 종가 기준 차트 커밋 |
| `pages.yml` | `docs/**` 변경 시 (main) | GitHub Pages 배포 |

## 리포트 생성 절차 (요약)

`hynix-report` 스킬이 다음 순서로 리포트를 만듭니다:

1. 날짜(KST) 확인 → 2. 시세 데이터 수집 → 3. 전일 OHLCV 확인 → 4. 최신 뉴스 Top 5 →
5. 실적·공시 → 6. 산업 동향(HBM·NAND) → 7. 증권사 의견 → 8. 차트(라이트/다크) 생성 →
9. 직전 리포트 참조 → 10. 리포트 MD 작성 → 11. 웹 빌드 + Artifact 재발행 → 12. 요약 보고

## GitHub Pages 설정

이 저장소를 처음 배포하려면 **Settings → Pages → Source = "GitHub Actions"** 로 한 번 설정해야 합니다.
이후 `docs/**` 변경이 push되면 `pages.yml`이 자동 배포합니다.
