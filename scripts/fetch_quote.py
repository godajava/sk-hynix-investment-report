#!/usr/bin/env python3
"""SK하이닉스(000660.KS) 시세 수집기 (의존성 없음, 야후 파이낸스 차트 API).

사용법:
    python3 scripts/fetch_quote.py [출력경로=docs/quote.json]

현재가·등락, 최근 2거래일 일봉(시가/고가/저가/종가/거래량), 그리고 6개월
일봉으로 계산한 기술적 지표(MACD, ATR, ADX, KDJ, 거래량/20일 이평)를
JSON으로 저장한다. GitHub Actions(quote.yml)가 장중 주기 실행해 Pages에
배포하고, 아침 리포트 루틴은 전일 상세 시세 표를 채우는 데 사용한다.
실패 시 비정상 종료해 기존 quote.json을 덮어쓰지 않는다.
"""
import json
import sys
import time
import urllib.request

URL = ("https://query1.finance.yahoo.com/v8/finance/chart/000660.KS"
       "?range=6mo&interval=1d")


def ema(vals, n):
    k = 2 / (n + 1)
    e = vals[0]
    out = [e]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def wilder_sum(vals, p):
    """Wilder 누적 평활 합 (ATR/DMI 표준)."""
    s = sum(vals[:p])
    out = [s]
    for v in vals[p:]:
        s = s - s / p + v
        out.append(s)
    return out


def compute_indicators(days):
    """일봉 배열(시간순)로 기술적 지표와 한국어 해석을 계산한다."""
    c = [d["close"] for d in days]
    h = [d["high"] for d in days]
    l = [d["low"] for d in days]
    v = [d["volume"] for d in days]
    n = len(c)
    ind = {}

    if n >= 35:  # MACD(12,26,9)
        macd = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
        sig = ema(macd, 9)
        m, s = macd[-1], sig[-1]
        ind["macd"] = {
            "macd": round(m), "signal": round(s), "hist": round(m - s),
            "read": "상승 모멘텀 (MACD > 시그널)" if m > s else "하락 모멘텀 (MACD < 시그널)",
        }

    if n >= 29:  # ATR(14) · ADX(14) — Wilder
        trs, pdm, ndm = [], [], []
        for i in range(1, n):
            trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
            up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
            pdm.append(up if up > dn and up > 0 else 0.0)
            ndm.append(dn if dn > up and dn > 0 else 0.0)
        tr14 = wilder_sum(trs, 14)
        pdi = [100 * a / b if b else 0 for a, b in zip(wilder_sum(pdm, 14), tr14)]
        ndi = [100 * a / b if b else 0 for a, b in zip(wilder_sum(ndm, 14), tr14)]
        dx = [100 * abs(a - b) / (a + b) if a + b else 0 for a, b in zip(pdi, ndi)]
        adx = sum(dx[:14]) / 14
        for x in dx[14:]:
            adx = (adx * 13 + x) / 14
        atr = tr14[-1] / 14
        ind["atr"] = {
            "value": round(atr), "pct": round(atr / c[-1] * 100, 1),
            "read": f"일 평균 변동폭 {atr / c[-1] * 100:.1f}%" + (" — 변동성 매우 큼" if atr / c[-1] > 0.05 else ""),
        }
        trend = "추세 강함" if adx >= 25 else ("추세 형성 중" if adx >= 20 else "추세 약함(횡보)")
        direction = "+DI 우위(상승)" if pdi[-1] > ndi[-1] else "-DI 우위(하락)"
        ind["adx"] = {"adx": round(adx, 1), "pdi": round(pdi[-1], 1), "ndi": round(ndi[-1], 1),
                      "read": f"{trend} · {direction}"}

    if n >= 15:  # KDJ(9,3,3)
        k = d_ = 50.0
        for i in range(8, n):
            h9, l9 = max(h[i - 8:i + 1]), min(l[i - 8:i + 1])
            rsv = (c[i] - l9) / (h9 - l9) * 100 if h9 > l9 else 50.0
            k = k * 2 / 3 + rsv / 3
            d_ = d_ * 2 / 3 + k / 3
        j = 3 * k - 2 * d_
        zone = "과매수 구간" if k > 80 else ("과매도 구간" if k < 20 else "중립 구간")
        cross = "K > D (단기 상승 우위)" if k > d_ else "K < D (단기 하락 우위)"
        ind["kdj"] = {"k": round(k, 1), "d": round(d_, 1), "j": round(j, 1),
                      "read": f"{zone} · {cross}"}

    if n >= 21:  # 거래량 vs 20일 이평
        vma20 = sum(v[-21:-1]) / 20  # 당일(진행 중) 제외한 직전 20일
        ratio = v[-1] / vma20 if vma20 else 0
        level = "급증" if ratio >= 2 else ("증가" if ratio >= 1.3 else ("평균 수준" if ratio >= 0.7 else "감소"))
        ind["volume"] = {"today": v[-1], "ma20": round(vma20),
                         "ratio": round(ratio, 2),
                         "read": f"20일 평균 대비 {ratio:.1f}배 — {level}"}
    return ind


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/quote.json"
    history_out = sys.argv[2] if len(sys.argv) > 2 else None
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)

    result = data["chart"]["result"][0]
    meta = result["meta"]
    ts = result.get("timestamp") or []
    q = result["indicators"]["quote"][0]

    days = []
    for i, t in enumerate(ts):
        if q["close"][i] is None:
            continue
        days.append({
            "date": time.strftime("%Y-%m-%d", time.gmtime(t + 9 * 3600)),  # KST
            "open": q["open"][i], "high": q["high"][i], "low": q["low"][i],
            "close": q["close"][i], "volume": q["volume"][i],
        })

    price = meta.get("regularMarketPrice")
    if not price or not days:
        sys.exit("오류: 시세 데이터 없음")

    # 전일 종가: 마지막 일봉이 당일(현재가와 같은 날) 봉이면 그 직전 봉의 종가.
    # meta의 chartPreviousClose는 조회 범위(5d) 직전 종가라 사용하지 않는다.
    market_date = time.strftime("%Y-%m-%d", time.gmtime(meta.get("regularMarketTime", 0) + 9 * 3600))
    if len(days) >= 2 and days[-1]["date"] == market_date:
        prev = days[-2]["close"]
    elif days[-1]["date"] != market_date:
        prev = days[-1]["close"]
    else:
        prev = None

    payload = {
        "symbol": "000660.KS",
        "price": price,
        "previousClose": prev,
        "change": round(price - prev) if prev else None,
        "changePercent": round((price - prev) / prev * 100, 2) if prev else None,
        "marketTime": time.strftime("%Y-%m-%d %H:%M KST",
                                    time.gmtime(meta.get("regularMarketTime", 0) + 9 * 3600)),
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M KST", time.gmtime(time.time() + 9 * 3600)),
        "days": days[-2:],  # [전일, 당일] 또는 [전전일, 전일]
        "indicators": compute_indicators(days),
    }
    with open(out, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    if history_out:
        with open(history_out, "w") as f:
            json.dump(days, f)
    print(f"저장: {out} — 현재가 {price:,.0f} ({payload['changePercent']}%), 일봉 {len(days)}개")


if __name__ == "__main__":
    main()
