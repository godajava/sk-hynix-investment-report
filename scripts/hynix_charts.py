#!/usr/bin/env python3
"""SK하이닉스 투자 리포트용 SVG 차트 생성기 (의존성 없음).

사용법:
    python3 scripts/hynix_charts.py <data.json> <출력_디렉터리> [--dark]

data.json 형식은 reports/sk-hynix/assets/ 아래 기존 파일을 참고.
생성 차트: price_trend / three_month_trend / target_prices / quarterly_earnings / hbm_share
색상은 dataviz 검증을 통과한 팔레트 고정값. --dark는 다크 서피스용
팔레트(#3987e5,#008300,#d55181 / dark, 검증 통과)로 전환한다.
"""
import json
import sys
import os

# 팔레트 (validate_palette.js 통과: light #2a78d6,#008300,#e87ba4)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"
GREEN = "#008300"
MAGENTA = "#e87ba4"

DARK = {  # validate_palette.js 통과: dark #3987e5,#008300,#d55181
    "SURFACE": "#1a1a19", "INK": "#ffffff", "INK2": "#c3c2b7", "MUTED": "#898781",
    "GRID": "#2c2c2a", "BASELINE": "#383835",
    "BLUE": "#3987e5", "GREEN": "#008300", "MAGENTA": "#d55181",
}
FONT = 'system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif'

W = 760


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_open(h, title, subtitle):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" font-family=\'{FONT}\'>',
        f'<rect width="{W}" height="{h}" fill="{SURFACE}" stroke="rgba(11,11,11,0.10)"/>',
        f'<text x="24" y="34" font-size="17" font-weight="700" fill="{INK}">{esc(title)}</text>',
        f'<text x="24" y="54" font-size="12" fill="{INK2}">{esc(subtitle)}</text>',
    ]


def svg_close(parts, h, source):
    parts.append(f'<text x="24" y="{h - 14}" font-size="10.5" fill="{MUTED}">{esc(source)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def rounded_bar_h(x, y, w, hgt, color, r=4, opacity=1.0):
    """가로 막대: 데이터 끝(오른쪽)만 4px 라운드, 기준선 쪽은 직각."""
    r = min(r, w / 2, hgt / 2)
    d = (f"M{x},{y} h{w - r} a{r},{r} 0 0 1 {r},{r} v{hgt - 2 * r} "
         f"a{r},{r} 0 0 1 -{r},{r} h-{w - r} z")
    return f'<path d="{d}" fill="{color}" opacity="{opacity}"/>'


def rounded_bar_v(x, y, w, hgt, color, r=4, extra=""):
    """세로 막대: 데이터 끝(위)만 4px 라운드."""
    r = min(r, w / 2, hgt / 2)
    d = (f"M{x},{y + hgt} v-{hgt - r} a{r},{r} 0 0 1 {r},-{r} h{w - 2 * r} "
         f"a{r},{r} 0 0 1 {r},{r} v{hgt - r} z")
    return f'<path d="{d}" fill="{color}" {extra}/>'


def fmt_price(v):
    return f"{v / 10000:,.0f}만"


def price_trend(d, out):
    """일별 종가 라인 차트. 역산치는 흰 채움(hollow) 마커로 구분."""
    h = 400
    pts = d["price_trend"]["points"]  # [{date, close, derived?, intraday?}]
    p = svg_open(h, d["price_trend"]["title"], d["price_trend"]["subtitle"])
    L, R, T, B = 88, 36, 84, 64
    pw, ph = W - L - R, h - T - B
    vals = [q["close"] for q in pts]
    lo = min(vals) * 0.97
    hi = max(vals) * 1.03
    step = 100000
    gy0 = int(lo // step + 1) * step
    ticks = list(range(gy0, int(hi) + 1, step))

    def X(i):
        return L + pw * i / (len(pts) - 1)

    def Y(v):
        return T + ph * (1 - (v - lo) / (hi - lo))

    for t in ticks:
        y = Y(t)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" '
                 f'style="font-variant-numeric:tabular-nums">{fmt_price(t)}</text>')
    p.append(f'<line x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}" stroke="{BASELINE}" stroke-width="1"/>')

    solid = [q for q in pts if not q.get("intraday")]
    path = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(q['close']):.1f}" for i, q in enumerate(solid))
    p.append(f'<path d="{path}" fill="none" stroke="{BLUE}" stroke-width="2"/>')
    if len(solid) < len(pts):  # 장중 구간은 점선 연결
        i0 = len(solid) - 1
        p.append(f'<path d="M{X(i0):.1f},{Y(pts[i0]["close"]):.1f} L{X(i0 + 1):.1f},{Y(pts[i0 + 1]["close"]):.1f}" '
                 f'fill="none" stroke="{BLUE}" stroke-width="2" stroke-dasharray="5 4"/>')

    lo_i = vals.index(min(vals))
    hi_i = vals.index(max(vals))
    for i, q in enumerate(pts):
        x, y = X(i), Y(q["close"])
        fill = SURFACE if (q.get("derived") or q.get("intraday")) else BLUE
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{fill}" stroke="{BLUE}" stroke-width="2"/>')
        p.append(f'<text x="{x:.1f}" y="{T + ph + 20}" font-size="11" fill="{MUTED}" text-anchor="middle">{esc(q["date"])}</text>')
        if i in (lo_i, hi_i, len(pts) - 1):
            dy = 22 if i == lo_i else -12
            p.append(f'<text x="{x:.1f}" y="{y + dy:.1f}" font-size="11.5" font-weight="600" fill="{INK2}" '
                     f'text-anchor="middle" style="font-variant-numeric:tabular-nums">{fmt_price(q["close"])}</text>')

    lx = L + pw - 240
    p.append(f'<circle cx="{lx}" cy="66" r="4.5" fill="{BLUE}" stroke="{BLUE}" stroke-width="2"/>')
    p.append(f'<text x="{lx + 10}" y="70" font-size="11" fill="{INK2}">확인 종가</text>')
    p.append(f'<circle cx="{lx + 80}" cy="66" r="4.5" fill="{SURFACE}" stroke="{BLUE}" stroke-width="2"/>')
    p.append(f'<text x="{lx + 90}" y="70" font-size="11" fill="{INK2}">역산·장중(점선)</text>')
    with open(os.path.join(out, "price_trend.svg"), "w") as f:
        f.write(svg_close(p, h, d["price_trend"]["source"]))


def three_month_trend(d, out):
    """3개월 앵커 종가 라인 + 최소제곱 선형 추세선. x축은 실제 날짜 간격 비례."""
    h = 400
    cfg = d["three_month_trend"]
    pts = cfg["points"]  # [{date, day, close, derived?}] day = 시작일부터 경과일
    p = svg_open(h, cfg["title"], cfg["subtitle"])
    L, R, T, B = 88, 36, 84, 64
    pw, ph = W - L - R, h - T - B
    vals = [q["close"] for q in pts]
    days = [q["day"] for q in pts]
    lo, hi = min(vals) * 0.95, max(vals) * 1.05
    step = 200000
    ticks = list(range(int(lo // step + 1) * step, int(hi) + 1, step))
    dmax = max(days)

    def X(day):
        return L + pw * day / dmax

    def Y(v):
        return T + ph * (1 - (v - lo) / (hi - lo))

    for t in ticks:
        y = Y(t)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" '
                 f'style="font-variant-numeric:tabular-nums">{fmt_price(t)}</text>')
    p.append(f'<line x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}" stroke="{BASELINE}" stroke-width="1"/>')

    # 최소제곱 추세선
    n = len(pts)
    mx, my = sum(days) / n, sum(vals) / n
    denom = sum((x - mx) ** 2 for x in days) or 1
    slope = sum((x - mx) * (y - my) for x, y in zip(days, vals)) / denom
    y0, y1 = my + slope * (0 - mx), my + slope * (dmax - mx)
    p.append(f'<path d="M{X(0):.1f},{Y(y0):.1f} L{X(dmax):.1f},{Y(y1):.1f}" fill="none" '
             f'stroke="{GREEN}" stroke-width="2" stroke-dasharray="7 5"/>')

    path = " ".join(f"{'M' if i == 0 else 'L'}{X(q['day']):.1f},{Y(q['close']):.1f}" for i, q in enumerate(pts))
    p.append(f'<path d="{path}" fill="none" stroke="{BLUE}" stroke-width="2"/>')
    lo_i, hi_i = vals.index(min(vals)), vals.index(max(vals))
    for i, q in enumerate(pts):
        x, y = X(q["day"]), Y(q["close"])
        fill = SURFACE if q.get("derived") else BLUE
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{fill}" stroke="{BLUE}" stroke-width="2"/>')
        if q.get("axis"):
            p.append(f'<text x="{x:.1f}" y="{T + ph + 20}" font-size="11" fill="{MUTED}" text-anchor="middle">{esc(q["date"])}</text>')
        if i in (0, lo_i, hi_i, n - 1):
            dy = 22 if i == lo_i else -12
            p.append(f'<text x="{x:.1f}" y="{y + dy:.1f}" font-size="11.5" font-weight="600" fill="{INK2}" '
                     f'text-anchor="middle" style="font-variant-numeric:tabular-nums">{fmt_price(q["close"])}</text>')

    trend_label = f"추세선 기울기: 일 {'+' if slope >= 0 else ''}{slope / 10000:.1f}만 원"
    lx = L + pw - 300
    p.append(f'<line x1="{lx}" y1="66" x2="{lx + 22}" y2="66" stroke="{BLUE}" stroke-width="2"/>')
    p.append(f'<text x="{lx + 28}" y="70" font-size="11" fill="{INK2}">종가(앵커)</text>')
    p.append(f'<line x1="{lx + 100}" y1="66" x2="{lx + 122}" y2="66" stroke="{GREEN}" stroke-width="2" stroke-dasharray="7 5"/>')
    p.append(f'<text x="{lx + 128}" y="70" font-size="11" fill="{INK2}">{esc(trend_label)}</text>')
    with open(os.path.join(out, "three_month_trend.svg"), "w") as f:
        f.write(svg_close(p, h, cfg["source"]))


def target_prices(d, out):
    """증권사 목표주가 가로 막대 + 현재가·컨센서스 기준선."""
    rows = d["target_prices"]["rows"]  # [{name, value, note?}]
    cur = d["target_prices"]["current"]
    cons = d["target_prices"]["consensus"]
    bh, gap = 26, 12
    h = 84 + len(rows) * (bh + gap) + 74
    p = svg_open(h, d["target_prices"]["title"], d["target_prices"]["subtitle"])
    L, R, T = 130, 96, 84
    pw = W - L - R
    vmax = max(max(r["value"] for r in rows), cur, cons) * 1.06

    def X(v):
        return L + pw * v / vmax

    plot_b = T + len(rows) * (bh + gap) - gap + 10
    for i, r in enumerate(rows):
        y = T + i * (bh + gap)
        p.append(f'<text x="{L - 10}" y="{y + bh / 2 + 4}" font-size="12" fill="{INK}" text-anchor="end">{esc(r["name"])}</text>')
        p.append(rounded_bar_h(L, y, X(r["value"]) - L, bh, BLUE))
        label = fmt_price(r["value"]) + (f' ({r["note"]})' if r.get("note") else "")
        p.append(f'<text x="{X(r["value"]) + 8:.1f}" y="{y + bh / 2 + 4}" font-size="11.5" font-weight="600" '
                 f'fill="{INK2}" style="font-variant-numeric:tabular-nums">{esc(label)}</text>')
    p.append(f'<line x1="{L}" y1="{T - 6}" x2="{L}" y2="{plot_b}" stroke="{BASELINE}" stroke-width="1"/>')
    for v, name, color in ((cur, "현재가", INK), (cons, "컨센서스", MUTED)):
        x = X(v)
        p.append(f'<line x1="{x:.1f}" y1="{T - 6}" x2="{x:.1f}" y2="{plot_b}" stroke="{color}" '
                 f'stroke-width="1.5" stroke-dasharray="4 3"/>')
        p.append(f'<text x="{x:.1f}" y="{plot_b + 18}" font-size="11" font-weight="600" fill="{color}" '
                 f'text-anchor="middle">{esc(name)} {fmt_price(v)}</text>')
    with open(os.path.join(out, "target_prices.svg"), "w") as f:
        f.write(svg_close(p, h, d["target_prices"]["source"]))


def quarterly_earnings(d, out):
    """분기 매출·영업이익 그룹 세로 막대 (단위 동일: 조 원, 단일 축)."""
    h = 420
    rows = d["quarterly_earnings"]["rows"]  # [{label, revenue, op, margin, estimate?}]
    p = svg_open(h, d["quarterly_earnings"]["title"], d["quarterly_earnings"]["subtitle"])
    L, R, T, B = 64, 36, 96, 80
    pw, ph = W - L - R, h - T - B
    vmax = max(r["revenue"] for r in rows) * 1.12
    ticks = range(0, int(vmax) + 1, 20)

    def Y(v):
        return T + ph * (1 - v / vmax)

    for t in ticks:
        y = Y(t)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" '
                 f'style="font-variant-numeric:tabular-nums">{t}조</text>')
    group_w = pw / len(rows)
    bw = min(56, group_w / 2 - 12)
    for i, r in enumerate(rows):
        cx = L + group_w * (i + 0.5)
        est = r.get("estimate")
        extra = f'stroke="{SURFACE}" stroke-width="0"' if not est else 'opacity="0.55" stroke-dasharray="4 3"'
        for j, (val, color) in enumerate(((r["revenue"], BLUE), (r["op"], GREEN))):
            x = cx - bw - 1 + j * (bw + 2)  # 인접 막대 사이 2px 서피스 간격
            bar_h = ph * val / vmax
            if est:
                p.append(rounded_bar_v(x, Y(val), bw, bar_h, color, extra=f'opacity="0.5"'))
                p.append(rounded_bar_v(x, Y(val), bw, bar_h, "none", extra=f'stroke="{color}" stroke-width="1.5" stroke-dasharray="4 3"'))
            else:
                p.append(rounded_bar_v(x, Y(val), bw, bar_h, color))
            p.append(f'<text x="{x + bw / 2:.1f}" y="{Y(val) - 7:.1f}" font-size="11" font-weight="600" fill="{INK2}" '
                     f'text-anchor="middle" style="font-variant-numeric:tabular-nums">{val:.1f}</text>')
        lbl = r["label"] + ("(E)" if est else "")
        p.append(f'<text x="{cx:.1f}" y="{T + ph + 22}" font-size="12" fill="{INK}" text-anchor="middle">{esc(lbl)}</text>')
        p.append(f'<text x="{cx:.1f}" y="{T + ph + 40}" font-size="11" fill="{MUTED}" text-anchor="middle">이익률 {r["margin"]}</text>')
    p.append(f'<line x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}" stroke="{BASELINE}" stroke-width="1"/>')
    lx = L + pw - 230
    p.append(f'<rect x="{lx}" y="60" width="12" height="12" rx="3" fill="{BLUE}"/>')
    p.append(f'<text x="{lx + 18}" y="70" font-size="11" fill="{INK2}">매출(조 원)</text>')
    p.append(f'<rect x="{lx + 92}" y="60" width="12" height="12" rx="3" fill="{GREEN}"/>')
    p.append(f'<text x="{lx + 110}" y="70" font-size="11" fill="{INK2}">영업이익 · 점선=전망</text>')
    with open(os.path.join(out, "quarterly_earnings.svg"), "w") as f:
        f.write(svg_close(p, h, d["quarterly_earnings"]["source"]))


def hbm_share(d, out):
    """HBM 점유율 추이 100% 누적 가로 막대 (세그먼트 간 2px 간격, 직접 레이블)."""
    rows = d["hbm_share"]["rows"]  # [{label, sk, samsung, micron}]
    bh, gap = 30, 14
    h = 118 + len(rows) * (bh + gap) + 44
    p = svg_open(h, d["hbm_share"]["title"], d["hbm_share"]["subtitle"])
    L, R, T = 110, 36, 108
    pw = W - L - R
    series = [("sk", "SK하이닉스", BLUE, "#ffffff"), ("samsung", "삼성전자", GREEN, "#ffffff"),
              ("micron", "마이크론", MAGENTA, INK)]
    lx = L
    for _, name, color, _tc in series:
        p.append(f'<rect x="{lx}" y="78" width="12" height="12" rx="3" fill="{color}"/>')
        p.append(f'<text x="{lx + 18}" y="88" font-size="11.5" fill="{INK2}">{esc(name)}</text>')
        lx += 30 + len(name) * 12
    for i, r in enumerate(rows):
        y = T + i * (bh + gap)
        p.append(f'<text x="{L - 10}" y="{y + bh / 2 + 4}" font-size="12" fill="{INK}" text-anchor="end">{esc(r["label"])}</text>')
        x = L
        for key, _name, color, tcolor in series:
            w = pw * r[key] / 100
            p.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{w - 2:.1f}" height="{bh}" rx="3" fill="{color}"/>')
            p.append(f'<text x="{x + w / 2:.1f}" y="{y + bh / 2 + 4}" font-size="11.5" font-weight="600" '
                     f'fill="{tcolor}" text-anchor="middle">{r[key]}%</text>')
            x += w
    with open(os.path.join(out, "hbm_share.svg"), "w") as f:
        f.write(svg_close(p, h, d["hbm_share"]["source"]))


def main():
    args = [a for a in sys.argv[1:] if a != "--dark"]
    if len(args) != 2:
        sys.exit(__doc__)
    if "--dark" in sys.argv:
        globals().update(DARK)
    with open(args[0]) as f:
        d = json.load(f)
    out = args[1]
    os.makedirs(out, exist_ok=True)
    for fn in (price_trend, three_month_trend, target_prices, quarterly_earnings, hbm_share):
        if fn.__name__ in d:
            fn(d, out)
            print(f"생성: {out}/{fn.__name__}.svg")


if __name__ == "__main__":
    main()
