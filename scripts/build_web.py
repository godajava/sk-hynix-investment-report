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


SENT = {
    "up": ("pos", "긍정", 1),
    "flat": ("neu", "중립", 0),
    "down": ("neg", "부정", -1),
}


def _sent(it):
    return SENT.get((it.get("signal") or {}).get("cls", "flat"), SENT["flat"])


def render_news(news_path="docs/news.json"):
    """docs/news.json을 읽어 '최신 뉴스 Top 10'의 감성 요약 카드와 뉴스 카드 <li>의
    정적 스냅샷을 만든다.

    웹 페이지는 loadNews() JS로 실시간 갱신되지만, Artifact(fetch 차단)에서는
    이 빌드 시점 스냅샷이 그대로 노출된다. loadNews()와 동일한 마크업을 생성한다.
    반환: (li들의 HTML, 감성 카드 HTML, fetchedAt 문자열)
    """
    if not os.path.exists(news_path):
        return "", "", ""
    try:
        data = json.load(open(news_path, encoding="utf-8"))
    except Exception:
        return "", "", ""
    items = data.get("items") or []
    e = html.escape
    lis = []
    for i, it in enumerate(items):
        cls, label, score = _sent(it)
        dt = (it.get("datetime") or it.get("date") or "").replace(" KST", "")
        src = f' <span class="nsrc">- {e(it["source"])}</span>' if it.get("source") else ""
        lis.append(
            f'<li><span class="nnum">{i + 1}</span><div>'
            f'<h3 class="ntitle">{e(it.get("title", ""))}{src} '
            f'<span class="pill {cls}">{label} ({score:+.1f})</span></h3>'
            + (f'<div class="ndate">{e(dt)}</div>' if dt else "")
            + (f'<p class="nsum">{e(it["summary"])}</p>' if it.get("summary") else "")
            + (f'<a class="nlink" href="{e(it["url"])}" target="_blank" rel="noopener">기사 전문 보기 →</a>'
               if it.get("url") else "")
            + "</div></li>")

    n = len(items)
    cnt = {"pos": 0, "neu": 0, "neg": 0}
    total = 0
    for it in items:
        cls, _, score = _sent(it)
        cnt[cls] += 1
        total += score
    avg = total / n if n else 0.0
    tot = "pos" if avg >= 0.3 else "neg" if avg <= -0.3 else "neu"
    tot_label = {"pos": "긍정", "neu": "중립", "neg": "부정"}[tot]
    seg = "".join(f'<span class="{k}" style="width:{100 * cnt[k] / n}%"></span>'
                  for k in ("pos", "neu", "neg") if cnt[k])
    legend = "".join(
        f'<span class="{k}"><i></i>{l} {cnt[k]}건 ({round(100 * cnt[k] / n) if n else 0}%)</span>'
        for k, l in (("pos", "긍정"), ("neu", "중립"), ("neg", "부정")))
    sent = (f'<p class="sent-title">뉴스 감성 분석 (최신 뉴스, TOP {n}건)</p>'
            f'<div class="sent-row"><span class="sent-label">종합 감성:</span>'
            f'<span class="sent-score {tot}">{tot_label} ({avg:+.2f})</span>'
            f'<div class="sent-bar">{seg}</div></div>'
            f'<div class="sent-legend">{legend}</div>') if n else ""
    return "".join(lis), sent, data.get("fetchedAt", "")


def build(date):
    tpl = open("scripts/report_template.html").read()

    # 최신 뉴스 Top 10: 빌드 시점 스냅샷을 새겨 넣는다(Artifact fetch 차단 대비).
    news_html, news_sent, news_when = render_news()
    if "__NEWS_TOP10__" in tpl:
        placeholder = ('<li><span class="nnum">·</span><div><h3 class="ntitle">뉴스 로딩 중… '
                       '구글 뉴스에서 SK하이닉스 최신 기사를 불러옵니다.</h3></div></li>')
        tpl = tpl.replace("__NEWS_TOP10__", news_html or placeholder)
    tpl = tpl.replace("__NEWS_SENT__", news_sent)
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
    artifact = tpl.replace("__TECH_CHARTS__", inline)
    open("reports/sk-hynix/latest.html", "w").write(artifact)
    print(f"생성: reports/sk-hynix/latest.html ({len(artifact):,} bytes, 기술차트 {len(inline_parts)}개 인라인)")

    os.makedirs("docs", exist_ok=True)
    imgs = "\n".join(
        f'<div class="chart"><img class="tech" src="charts/{name}.svg" alt="{name}" '
        f'style="display:block;width:100%"></div>' for name in TECH_CHARTS)
    pages = tpl.replace("__TECH_CHARTS__", imgs)
    favicon = (
        "data:image/svg+xml,"
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Ccircle cx='16' cy='16' r='16' fill='%232a6fd0'/%3E"
        "%3Cpath d='M8 20 L13 13 L18 17 L24 8' stroke='white' stroke-width='2.6' "
        "fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
    )
    desc = "SK하이닉스(KRX 000660) 실시간 투자 리포트 — 시세·기술적 지표·밸류에이션·투자 판단을 평일 장중 자동 갱신합니다."
    open("docs/index.html", "w").write(
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex\">"
        f"<meta name=\"description\" content=\"{desc}\">"
        "<meta property=\"og:type\" content=\"website\">"
        "<meta property=\"og:locale\" content=\"ko_KR\">"
        "<meta property=\"og:site_name\" content=\"SK하이닉스 투자 리포트\">"
        "<meta property=\"og:title\" content=\"SK하이닉스 투자 리포트\">"
        f"<meta property=\"og:description\" content=\"{desc}\">"
        f"<link rel=\"icon\" href=\"{favicon}\">"
        "</head><body>" + pages + "</body></html>"
    )
    print(f"생성: docs/index.html ({len(pages):,} bytes, 기술차트 img 참조)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    build(sys.argv[1])
