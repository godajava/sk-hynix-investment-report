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
import json
import html

MARKERS = {
    "__PRICE_TREND__": "price_trend.svg",
    "__TREND3M__": "three_month_trend.svg",
    "__QUARTERLY__": "quarterly_earnings.svg",
    "__HBM__": "hbm_share.svg",
    "__TARGETS__": "target_prices.svg",
}

# 기술 차트 (tech_charts.py 생성, docs/charts/에 커밋·배포됨)
TECH_CHARTS = ["candle_volume", "macd", "kdj", "adx_atr", "atr"]

# 실시간 시세 안내 패널.
# 2026-08-12 실측: TradingView는 KRX 시세를 익명 사용자에게 주지 않고
# (scanner API가 lp/ch/chp = null, update_mode=delayed_streaming_1200),
# 야후 chart API는 CORS 헤더가 없어 브라우저 직접 조회가 불가하다.
# 따라서 페이지 내 실시간 표시는 포기하고, 실시간은 외부 링크로 안내한다.
# 외부 스크립트가 없으므로 Pages·Artifact 동일 마크업을 쓴다.
NAVER_URL = "https://finance.naver.com/item/main.naver?code=000660"
TOSS_URL = "https://www.tossinvest.com/stocks/A000660/order"

LIVE_QUOTE_PANEL = """<div class="tv-wrap">
  <p class="tv-lead">
    이 리포트의 시세는 <strong>야후 파이낸스 수집분(약 20분 지연)</strong>입니다.
    체결 기준 <strong>실시간 시세</strong>는 아래에서 바로 확인하세요.
  </p>
  <div class="tv-links">
    <a class="tv-btn primary" href="__NAVER__" target="_blank" rel="noopener">네이버 금융 실시간 ↗</a>
    <a class="tv-btn" href="__TOSS__" target="_blank" rel="noopener">토스증권 ↗</a>
    <a class="tv-btn" href="https://m.stock.naver.com/domestic/stock/000660/total" target="_blank" rel="noopener">네이버 모바일 ↗</a>
  </div>
  <p class="tv-note">
    ※ TradingView·야후 등 무료 임베드 위젯은 KRX 시세를 익명 사용자에게 제공하지 않아
    (TradingView는 <code>delayed_streaming_1200</code>으로 값이 비어 옴) 페이지 내 실시간 표시는 불가능합니다.
    상단 헤더 수치는 수집 시각과 함께 표시되며, 새로고침으로 최신 수집분을 다시 불러옵니다.
  </p>
</div>"""

LIVE_WIDGET_PAGES = LIVE_QUOTE_PANEL.replace("__NAVER__", NAVER_URL).replace("__TOSS__", TOSS_URL)
LIVE_WIDGET_ARTIFACT = LIVE_WIDGET_PAGES


def render_news(news_path="docs/news.json"):
    """docs/news.json을 읽어 '최신 뉴스 Top 10'의 정적 <li> 스냅샷을 만든다.

    웹 페이지는 loadNews() JS로 실시간 갱신되지만, Artifact(fetch 차단)에서는
    이 빌드 시점 스냅샷이 그대로 노출된다. loadNews()와 동일한 마크업을 생성한다.
    반환: (li들의 HTML, fetchedAt 문자열)
    """
    if not os.path.exists(news_path):
        return "", ""
    try:
        data = json.load(open(news_path, encoding="utf-8"))
    except Exception:
        return "", ""
    items = data.get("items") or []
    e = html.escape
    lis = []
    for it in items:
        sig = it.get("signal") or {"cls": "flat", "label": "중립", "emoji": "⚪"}
        chip = (f'<span class="chip {e(sig.get("cls", "flat"))}">'
                f'{e(sig.get("emoji", "⚪"))} {e(sig.get("label", "중립"))}</span> ')
        date = (f'<span class="chip flat" style="font-variant-numeric:tabular-nums">'
                f'{e(it.get("date", ""))}</span> ') if it.get("date") else ""
        src = (f' <span style="color:var(--muted)">· {e(it.get("source", ""))}</span>'
               if it.get("source") else "")
        t = e(it.get("title", ""))
        url = it.get("url", "")
        title = (f'<a href="{e(url)}" target="_blank" rel="noopener">{t}</a>'
                 if url else t)
        lis.append(f"<li><div><h3>{chip}{date}{title}{src}</h3></div></li>")
    return "".join(lis), data.get("fetchedAt", "")


def build(date):
    tpl = open("scripts/report_template.html").read()

    # 최신 뉴스 Top 10: 빌드 시점 스냅샷을 새겨 넣는다(Artifact fetch 차단 대비).
    news_html, news_when = render_news()
    if "__NEWS_TOP10__" in tpl:
        placeholder = ('<li><div><h3><span class="chip flat">뉴스 로딩 중…</span> '
                       '구글 뉴스에서 SK하이닉스 최신 기사를 불러옵니다.</h3></div></li>')
        tpl = tpl.replace("__NEWS_TOP10__", news_html or placeholder)
    if news_when:
        tpl = tpl.replace(
            '<span id="news-feed-when"></span>',
            f'<span id="news-feed-when">수집 {html.escape(news_when)}</span>')

    # 라이트 테마: 마커 차트는 라이트 세트(assets/{date}/)를 인라인
    chart_dir = f"reports/sk-hynix/assets/{date}/"
    for marker, fn in MARKERS.items():
        path = chart_dir + fn
        if marker in tpl:
            if not os.path.exists(path):
                sys.exit(f"오류: {path} 없음 — 먼저 hynix_charts.py 실행 필요")
            tpl = tpl.replace(marker, open(path).read())

    # 아티팩트: 커밋된 SVG를 인라인 (발행 시점 스냅샷)
    inline_parts = []
    for name in TECH_CHARTS:
        path = f"docs/charts/{name}.svg"
        if os.path.exists(path):
            inline_parts.append(f'<div class="chart">{open(path).read()}</div>')
    inline = "\n".join(inline_parts) if inline_parts else \
        '<p style="color:var(--muted)">차트 준비 중 — 다음 장중 갱신 때 표시됩니다.</p>'
    artifact = tpl.replace("__TECH_CHARTS__", inline) \
                  .replace("__LIVE_WIDGET__", LIVE_WIDGET_ARTIFACT)
    open("reports/sk-hynix/latest.html", "w").write(artifact)
    print(f"생성: reports/sk-hynix/latest.html ({len(artifact):,} bytes, 기술차트 {len(inline_parts)}개 인라인)")

    os.makedirs("docs", exist_ok=True)
    imgs = "\n".join(
        f'<div class="chart"><img class="tech" src="charts/{name}.svg" alt="{name}" '
        f'style="display:block;width:100%"></div>' for name in TECH_CHARTS)
    pages = tpl.replace("__TECH_CHARTS__", imgs) \
               .replace("__LIVE_WIDGET__", LIVE_WIDGET_PAGES)
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
