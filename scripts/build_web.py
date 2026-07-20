#!/usr/bin/env python3
"""SK하이닉스 리포트 웹 페이지 빌더.

사용법:
    python3 scripts/build_web.py <YYYY-MM-DD>

scripts/report_template.html에 당일 다크 차트 SVG를 인라인하고 두 버전을 생성한다:
  - reports/sk-hynix/latest.html  : Claude Artifact용 (기술 차트를 인라인 —
    발행 시점 스냅샷)
  - docs/index.html               : GitHub Pages용 (기술 차트를 <img>로 참조 —
    quote.yml/charts.yml이 배포할 때마다 자동 최신화)
"""
import sys
import os

MARKERS = {
    "__PRICE_TREND__": "price_trend.svg",
    "__TREND3M__": "three_month_trend.svg",
    "__QUARTERLY__": "quarterly_earnings.svg",
    "__HBM__": "hbm_share.svg",
    "__TARGETS__": "target_prices.svg",
}

# 기술 차트 (tech_charts.py 생성, docs/charts/에 커밋·배포됨)
TECH_CHARTS = ["candle_volume", "macd", "kdj", "adx_atr", "atr"]


def build(date):
    tpl = open("scripts/report_template.html").read()
    dark_dir = f"reports/sk-hynix/assets/{date}/dark/"
    for marker, fn in MARKERS.items():
        path = dark_dir + fn
        if marker in tpl:
            if not os.path.exists(path):
                sys.exit(f"오류: {path} 없음 — 먼저 hynix_charts.py --dark 실행 필요")
            tpl = tpl.replace(marker, open(path).read())

    # 아티팩트: 커밋된 SVG를 인라인 (발행 시점 스냅샷)
    inline_parts = []
    for name in TECH_CHARTS:
        path = f"docs/charts/{name}.svg"
        if os.path.exists(path):
            inline_parts.append(f'<div class="chart">{open(path).read()}</div>')
    inline = "\n".join(inline_parts) if inline_parts else \
        '<p style="color:var(--muted)">차트 준비 중 — 다음 장중 갱신 때 표시됩니다.</p>'
    artifact = tpl.replace("__TECH_CHARTS__", inline)
    open("reports/sk-hynix/latest.html", "w").write(artifact)
    print(f"생성: reports/sk-hynix/latest.html ({len(artifact):,} bytes, 기술차트 {len(inline_parts)}개 인라인)")

    os.makedirs("docs", exist_ok=True)
    imgs = "\n".join(
        f'<div class="chart"><img class="tech" src="charts/{name}.svg" alt="{name}" '
        f'style="display:block;width:100%"></div>' for name in TECH_CHARTS)
    pages = tpl.replace("__TECH_CHARTS__", imgs)
    open("docs/index.html", "w").write(
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex\">"
        "</head><body>" + pages + "</body></html>"
    )
    print(f"생성: docs/index.html ({len(pages):,} bytes, 기술차트 img 참조)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    build(sys.argv[1])
