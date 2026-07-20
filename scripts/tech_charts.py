#!/usr/bin/env python3
"""SK하이닉스 기술적 분석 SVG 차트 생성기 (다크 전용, 의존성 없음).

사용법:
    python3 scripts/tech_charts.py <history.json> <출력_디렉터리>

history.json은 fetch_quote.py의 두 번째 인자로 저장한 일봉 배열.
생성 차트 (최근 3개월 표시):
  candle_volume.svg — 일봉 캔들 + 거래량(20일 이평선)
  macd.svg          — MACD(12,26,9) 라인·시그널·히스토그램
  kdj.svg           — KDJ(9,3,3) + 과매수/과매도 밴드
  adx_atr.svg       — ADX/DMI(14) + ATR(14)

캔들 색은 국내 관례(상승 빨강 / 하락 파랑)를 따르며, 두 색과 보조선
색은 다크 서피스 기준 dataviz 검증을 통과한 팔레트 값이다.
"""
import json
import sys
import os
from fetch_quote import ema, wilder_sum

# 다크 팔레트 (validate_palette.js --mode dark 통과 값)
SURFACE = "#1a1a19"
INK = "#ffffff"
INK2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
BASELINE = "#383835"
UP = "#e66767"      # 상승(국내 관례 빨강, 다크 슬롯8)
DOWN = "#3987e5"    # 하락(파랑, 다크 슬롯1)
GREEN = "#008300"
MAGENTA = "#d55181"
FONT = 'system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif'
W = 760
SHOW = 66  # 표시 봉 수 (약 3개월)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def head(h, title, subtitle):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" font-family=\'{FONT}\'>',
        f'<rect width="{W}" height="{h}" fill="{SURFACE}"/>',
        f'<text x="20" y="28" font-size="14.5" font-weight="700" fill="{INK}">{esc(title)}</text>',
        f'<text x="20" y="46" font-size="11" fill="{INK2}">{esc(subtitle)}</text>',
    ]


def legend(p, items, y=28):
    """우측 상단 범례: [(색, 라벨, 점선여부)]"""
    x = W - 20 - sum(30 + len(lbl) * 11 for _, lbl, _ in items)
    for color, lbl, dash in items:
        d = ' stroke-dasharray="4 3"' if dash else ""
        p.append(f'<line x1="{x}" y1="{y - 4}" x2="{x + 18}" y2="{y - 4}" stroke="{color}" stroke-width="2"{d}/>')
        p.append(f'<text x="{x + 23}" y="{y}" font-size="10.5" fill="{INK2}">{esc(lbl)}</text>')
        x += 30 + len(lbl) * 11


def x_axis(p, dates, L, pw, y):
    n = len(dates)
    step = max(1, n // 6)
    for i in range(0, n, step):
        x = L + pw * (i + 0.5) / n
        mmdd = dates[i][5:].replace("-", "/")
        p.append(f'<text x="{x:.1f}" y="{y}" font-size="10" fill="{MUTED}" text-anchor="middle">{mmdd}</text>')


def grid_y(p, L, pw, T, ph, vmin, vmax, fmt, ticks=4):
    for i in range(ticks + 1):
        v = vmin + (vmax - vmin) * i / ticks
        y = T + ph * (1 - i / ticks)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{L - 6}" y="{y + 3.5:.1f}" font-size="10" fill="{MUTED}" text-anchor="end" '
                 f'style="font-variant-numeric:tabular-nums">{fmt(v)}</text>')


def line_path(xs, ys, Y):
    parts, pen = [], False
    for x, v in zip(xs, ys):
        if v is None:
            pen = False
            continue
        parts.append(f"{'L' if pen else 'M'}{x:.1f},{Y(v):.1f}")
        pen = True
    return " ".join(parts)


def fmt_man(v):
    return f"{v / 10000:,.0f}만"


def candle_volume(days, out):
    n = len(days)
    h = 560
    L, R, T = 64, 20, 64
    pw = W - L - R
    price_h, vol_t, vol_h, B = 330, 470, 60, 26
    p = head(h, "일봉 차트 (최근 3개월)", "원. 상승=빨강 / 하락=파랑 (국내 관례). 아래: 거래량과 20일 이평선.")
    legend(p, [(UP, "상승", False), (DOWN, "하락", False), (GREEN, "거래량 MA20", False)])

    hi = max(d["high"] for d in days) * 1.02
    lo = min(d["low"] for d in days) * 0.98

    def Y(v):
        return T + price_h * (1 - (v - lo) / (hi - lo))

    grid_y(p, L, pw, T, price_h, lo, hi, fmt_man)
    bw = pw / n * 0.66
    for i, d in enumerate(days):
        x = L + pw * (i + 0.5) / n
        color = UP if d["close"] >= d["open"] else DOWN
        p.append(f'<line x1="{x:.1f}" y1="{Y(d["high"]):.1f}" x2="{x:.1f}" y2="{Y(d["low"]):.1f}" stroke="{color}" stroke-width="1.2"/>')
        top, bot = max(d["open"], d["close"]), min(d["open"], d["close"])
        bh = max(1.2, Y(bot) - Y(top))
        p.append(f'<rect x="{x - bw / 2:.1f}" y="{Y(top):.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}"/>')
    last = days[-1]["close"]
    p.append(f'<text x="{L + pw - 4}" y="{Y(last) - 6:.1f}" font-size="11" font-weight="700" fill="{INK}" '
             f'text-anchor="end" style="font-variant-numeric:tabular-nums">{fmt_man(last)}</text>')

    vols = [d["volume"] for d in days]
    vmax = max(vols) * 1.1
    vma = [None] * len(vols)
    for i in range(19, len(vols)):
        vma[i] = sum(vols[i - 19:i + 1]) / 20
    p.append(f'<line x1="{L}" y1="{vol_t}" x2="{L + pw}" y2="{vol_t}" stroke="{BASELINE}" stroke-width="1"/>')
    p.append(f'<text x="{L - 6}" y="{vol_t + 10}" font-size="10" fill="{MUTED}" text-anchor="end">거래량</text>')
    for i, d in enumerate(days):
        x = L + pw * (i + 0.5) / n
        color = UP if d["close"] >= d["open"] else DOWN
        bh = vol_h * d["volume"] / vmax
        p.append(f'<rect x="{x - bw / 2:.1f}" y="{vol_t + vol_h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.55"/>')
    xs = [L + pw * (i + 0.5) / n for i in range(n)]
    p.append(f'<path d="{line_path(xs, vma, lambda v: vol_t + vol_h * (1 - v / vmax))}" fill="none" stroke="{GREEN}" stroke-width="2"/>')
    x_axis(p, [d["date"] for d in days], L, pw, vol_t + vol_h + 18)
    p.append("</svg>")
    with open(os.path.join(out, "candle_volume.svg"), "w") as f:
        f.write("\n".join(p))


def panel(title, subtitle, dates, series, fmt, guides=None, h=250):
    """공용 지표 패널: series = [(라벨, 색, 값리스트, 점선여부)]"""
    L, R, T, B = 64, 20, 64, 30
    pw, ph = W - L - R, h - T - B
    p = head(h, title, subtitle)
    legend(p, [(c, lbl, d) for lbl, c, _, d in series])
    vals = [v for _, _, vs, _ in series for v in vs if v is not None]
    vmax, vmin = max(vals), min(vals)
    pad = (vmax - vmin) * 0.08 or 1
    vmax += pad
    vmin -= pad

    def Y(v):
        return T + ph * (1 - (v - vmin) / (vmax - vmin))

    grid_y(p, L, pw, T, ph, vmin, vmax, fmt, ticks=3)
    if guides:
        for gv, glabel in guides:
            if vmin < gv < vmax:
                p.append(f'<line x1="{L}" y1="{Y(gv):.1f}" x2="{L + pw}" y2="{Y(gv):.1f}" '
                         f'stroke="{MUTED}" stroke-width="1" stroke-dasharray="3 4"/>')
                p.append(f'<text x="{L + pw + 2}" y="{Y(gv) + 3:.1f}" font-size="9" fill="{MUTED}">{esc(glabel)}</text>')
    n = len(dates)
    xs = [L + pw * (i + 0.5) / n for i in range(n)]
    for lbl, color, vs, dash in series:
        d = ' stroke-dasharray="4 3"' if dash else ""
        p.append(f'<path d="{line_path(xs, vs, Y)}" fill="none" stroke="{color}" stroke-width="1.8"{d}/>')
    x_axis(p, dates, L, pw, T + ph + 18)
    return p, Y, xs, (L, pw, T, ph, vmin, vmax)


def macd_chart(days, out):
    c = [d["close"] for d in days]
    macd = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
    sig = ema(macd, 9)
    hist = [m - s for m, s in zip(macd, sig)]
    sl = slice(-SHOW, None)
    dates = [d["date"] for d in days][sl]
    p, Y, xs, geo = panel("MACD (12,26,9)", "원. 막대 = 히스토그램(MACD - 시그널).",
                          dates, [("MACD", DOWN, macd[sl], False), ("시그널", GREEN, sig[sl], False)],
                          lambda v: f"{v / 10000:+,.0f}만", guides=[(0, "0")])
    n = len(dates)
    L, pw, T, ph, vmin, vmax = geo
    bw = pw / n * 0.5
    for x, hv in zip(xs, hist[sl]):
        color = UP if hv >= 0 else DOWN
        y0, y1 = Y(0), Y(hv)
        p.insert(6, f'<rect x="{x - bw / 2:.1f}" y="{min(y0, y1):.1f}" width="{bw:.1f}" '
                    f'height="{max(1, abs(y1 - y0)):.1f}" fill="{color}" opacity="0.4"/>')
    p.append("</svg>")
    with open(os.path.join(out, "macd.svg"), "w") as f:
        f.write("\n".join(p))


def kdj_chart(days, out):
    c = [d["close"] for d in days]
    h_, l_ = [d["high"] for d in days], [d["low"] for d in days]
    n = len(c)
    K = [None] * n
    D = [None] * n
    J = [None] * n
    k = dv = 50.0
    for i in range(8, n):
        h9, l9 = max(h_[i - 8:i + 1]), min(l_[i - 8:i + 1])
        rsv = (c[i] - l9) / (h9 - l9) * 100 if h9 > l9 else 50.0
        k = k * 2 / 3 + rsv / 3
        dv = dv * 2 / 3 + k / 3
        K[i], D[i], J[i] = k, dv, 3 * k - 2 * dv
    sl = slice(-SHOW, None)
    dates = [d["date"] for d in days][sl]
    p, *_ = panel("KDJ (9,3,3)", "80 이상 과매수 · 20 이하 과매도.",
                  dates, [("K", DOWN, K[sl], False), ("D", GREEN, D[sl], False), ("J", MAGENTA, J[sl], True)],
                  lambda v: f"{v:.0f}", guides=[(80, "80"), (20, "20")])
    p.append("</svg>")
    with open(os.path.join(out, "kdj.svg"), "w") as f:
        f.write("\n".join(p))


def adx_atr_chart(days, out):
    c = [d["close"] for d in days]
    h_, l_ = [d["high"] for d in days], [d["low"] for d in days]
    n = len(c)
    trs, pdm, ndm = [], [], []
    for i in range(1, n):
        trs.append(max(h_[i] - l_[i], abs(h_[i] - c[i - 1]), abs(l_[i] - c[i - 1])))
        up, dn = h_[i] - h_[i - 1], l_[i - 1] - l_[i]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
    tr14 = wilder_sum(trs, 14)
    pdi = [100 * a / b if b else 0 for a, b in zip(wilder_sum(pdm, 14), tr14)]
    ndi = [100 * a / b if b else 0 for a, b in zip(wilder_sum(ndm, 14), tr14)]
    dx = [100 * abs(a - b) / (a + b) if a + b else 0 for a, b in zip(pdi, ndi)]
    adx = [None] * len(dx)
    a = sum(dx[:14]) / 14
    adx[13] = a
    for i in range(14, len(dx)):
        a = (a * 13 + dx[i]) / 14
        adx[i] = a

    def pad(vs, offset):  # 원본 days 길이에 맞춰 앞을 None으로 채움
        return [None] * offset + list(vs)

    sl = slice(-SHOW, None)
    dates = [d["date"] for d in days][sl]
    p, *_ = panel("ADX / DMI (14)", "ADX 25 이상 = 추세 강함. +DI/-DI 교차가 방향 신호.",
                  dates, [("ADX", INK2, pad(adx, 14)[sl], False),
                          ("+DI", UP, pad(pdi, 14)[sl], False), ("-DI", DOWN, pad(ndi, 14)[sl], False)],
                  lambda v: f"{v:.0f}", guides=[(25, "25")])
    p.append("</svg>")
    with open(os.path.join(out, "adx_atr.svg"), "w") as f:
        f.write("\n".join(p))

    atr = [s / 14 for s in tr14]
    p, *_ = panel("ATR (14)", "원. 일 평균 변동폭 — 높을수록 변동성 큼.",
                  dates, [("ATR", MAGENTA, pad(atr, 14)[sl], False)], fmt_man)
    p.append("</svg>")
    with open(os.path.join(out, "atr.svg"), "w") as f:
        f.write("\n".join(p))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        days = json.load(f)
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    shown = days[-SHOW:]
    candle_volume(shown, out)
    macd_chart(days, out)
    kdj_chart(days, out)
    adx_atr_chart(days, out)
    for f_ in ("candle_volume", "macd", "kdj", "adx_atr", "atr"):
        print(f"생성: {out}/{f_}.svg")


if __name__ == "__main__":
    main()
