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

# 실시간 시세 위젯(TradingView) — GitHub Pages 전용.
# Artifact는 CSP로 외부 스크립트가 차단되므로 정적 안내로 대체한다.
NAVER_URL = "https://finance.naver.com/item/main.naver?code=000660"
TOSS_URL = "https://www.tossinvest.com/stocks/A000660/order"

LIVE_WIDGET_PAGES = """<div class="tv-wrap">
  <div class="tradingview-widget-container" id="tv-widget">
    <div class="tradingview-widget-container__widget"></div>
    <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-info.js" async>
    {"symbol":"KRX:000660","width":"100%","locale":"kr","colorTheme":"light","isTransparent":true}
    </script>
  </div>
  <p class="tv-fallback" id="tv-fallback">
    <strong>실시간 위젯을 불러오지 못했습니다</strong>
    네트워크나 브라우저 확장으로 차단됐을 수 있습니다 —
    <a href="__NAVER__" target="_blank" rel="noopener">네이버 금융</a> ·
    <a href="__TOSS__" target="_blank" rel="noopener">토스증권</a>에서 확인하세요.
  </p>
</div>
<p class="tv-note">
  위 위젯은 TradingView가 직접 제공하는 시세로, 위젯 안에 표시되는 시각·지연 여부가 기준입니다.
  아래 리포트 본문의 수치는 야후 파이낸스 수집분(약 20분 지연)이라 두 값이 다를 수 있습니다.
  <a href="https://kr.tradingview.com/symbols/KRX-000660/" target="_blank" rel="noopener nofollow">TradingView에서 보기</a>
</p>
<script>
  // 위젯이 4초 안에 렌더되지 않으면(차단·오프라인) 대체 안내를 노출한다.
  (function () {
    var box = document.getElementById("tv-widget");
    var fb = document.getElementById("tv-fallback");
    if (!box || !fb) return;
    setTimeout(function () {
      if (!box.querySelector("iframe")) fb.style.display = "block";
    }, 4000);
  })();
</script>""".replace("__NAVER__", NAVER_URL).replace("__TOSS__", TOSS_URL)

LIVE_WIDGET_ARTIFACT = """<div class="tv-wrap">
  <p class="tv-fallback" style="display:block">
    <strong>실시간 시세는 웹 페이지에서 제공됩니다</strong>
    이 문서(Artifact)는 보안 정책상 외부 시세 위젯을 표시할 수 없습니다 —
    <a href="https://godajava.github.io/sk-hynix-investment-report/" target="_blank" rel="noopener">웹 리포트</a> ·
    <a href="__NAVER__" target="_blank" rel="noopener">네이버 금융</a> ·
    <a href="__TOSS__" target="_blank" rel="noopener">토스증권</a>에서 확인하세요.
  </p>
</div>""".replace("__NAVER__", NAVER_URL).replace("__TOSS__", TOSS_URL)


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
