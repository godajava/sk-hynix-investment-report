#!/usr/bin/env python3
"""SK하이닉스(000660.KS) 시세 수집기 (의존성 없음, 야후 파이낸스 차트 API).

사용법:
    python3 scripts/fetch_quote.py [출력경로=docs/quote.json]

현재가·등락, 최근 2거래일 일봉(시가/고가/저가/종가/거래량), 그리고 6개월
일봉으로 계산한 기술적 지표(MACD, ATR, ADX, KDJ, 거래량/20일 이평)를
JSON으로 저장한다. GitHub Actions(quote.yml)가 장중 주기 실행해 Pages에
배포하고, 아침 리포트 루틴은 전일 상세 시세 표를 채우는 데 사용한다.
실패 시 비정상 종료해 기존 quote.json을 덮어쓰지 않는다.

[2026-10-13 보강] 야후 일봉에서 직전 거래일 봉이 통째로 빠지는 경우가 확인됐다
(10/12 봉 누락 → 전일 종가가 10/8로 잡혀 10/13 등락률이 -10.29%로 표시, 지표도 왜곡).
  1) 일봉에 없는 거래일은 5분봉(range=5d)을 일 단위로 집계해 복원한다(synthetic=true).
  2) 전일 종가를 트레이딩뷰 스캐너(KRX:000660의 close-change_abs)로 교차 검증하고,
     야후 일봉 기반 값과 0.2% 넘게 다르면 트레이딩뷰 값을 쓴다(previousCloseSource).
  3) 복원·보정 내역은 repairedDays / warnings 에 남긴다. 어느 보강이 실패해도 기존 동작은 유지.
"""
import json
import sys
import time
import urllib.request

URL = ("https://query1.finance.yahoo.com/v8/finance/chart/000660.KS"
       "?range=6mo&interval=1d")
INTRADAY_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/000660.KS"
                "?range=5d&interval=5m")
UA = {"User-Agent": "Mozilla/5.0"}
PREV_MISMATCH = 0.002  # 야후 전일 종가 vs 트레이딩뷰 전일 종가 허용 오차(0.2%)


def kst_date(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t + 9 * 3600))


def parse_bars(ts, q):
    """야후 chart 응답 → (유효 일봉 리스트, 종가 None인 날짜 리스트)."""
    days, skipped = [], []
    for i, t in enumerate(ts):
        if q["close"][i] is None:
            skipped.append(kst_date(t))
            continue
        days.append({
            "date": kst_date(t),
            "open": q["open"][i], "high": q["high"][i], "low": q["low"][i],
            "close": q["close"][i], "volume": q["volume"][i],
        })
    return days, skipped


def daily_from_intraday(ts, q):
    """분봉 → KST 일자별 일봉 {date: bar}. 값이 None인 분봉은 건너뛴다."""
    by = {}
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        o = q["open"][i] if q["open"][i] is not None else c
        h = q["high"][i] if q["high"][i] is not None else c
        l = q["low"][i] if q["low"][i] is not None else c
        v = q["volume"][i] or 0
        d = kst_date(t)
        b = by.get(d)
        if b is None:
            by[d] = {"date": d, "open": o, "high": h, "low": l, "close": c, "volume": v}
        else:
            b["high"] = max(b["high"], h)
            b["low"] = min(b["low"], l)
            b["close"] = c  # 시간순이므로 마지막 분봉 종가
            b["volume"] += v
    return by


def merge_missing_days(days, intraday_days):
    """일봉에 없는 거래일을 분봉 집계로 채운다. 반환: (병합 일봉, 복원 날짜 리스트)."""
    have = {d["date"] for d in days}
    first = days[0]["date"] if days else ""
    added = []
    for d, b in intraday_days.items():
        if d not in have and d >= first:
            nb = dict(b)
            nb["synthetic"] = True
            days.append(nb)
            added.append(d)
    days.sort(key=lambda x: x["date"])
    return days, sorted(added)


def pick_prev(days, market_date, tv_prev):
    """전일 종가와 출처를 정한다. 야후 일봉 기반 값을 트레이딩뷰 값으로 교차 검증."""
    if len(days) >= 2 and days[-1]["date"] == market_date:
        prev = days[-2]["close"]
    elif days and days[-1]["date"] != market_date:
        prev = days[-1]["close"]
    else:
        prev = None
    src = "yahoo-daily"
    warn = None
    if tv_prev:
        if prev is None:
            prev, src = tv_prev, "tradingview"
        elif abs(prev - tv_prev) / tv_prev > PREV_MISMATCH:
            warn = (f"전일 종가 불일치: 야후 일봉 기반 {prev:,.0f} vs 트레이딩뷰 {tv_prev:,.0f} "
                    "→ 트레이딩뷰 값 사용")
            prev, src = tv_prev, "tradingview"
        else:
            src = "yahoo-daily+tradingview-ok"
    return prev, src, warn


def tv_prev_close():
    """트레이딩뷰 스캐너로 전일 종가(close - change_abs). 실패하면 None."""
    try:
        from fetch_night import tv_scan
        r = tv_scan(["KRX:000660"], ["close", "change_abs"]).get("KRX:000660")
        if r and r.get("close") and r.get("change_abs") is not None:
            return float(r["close"]) - float(r["change_abs"])
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 트레이딩뷰 전일 종가 조회 실패: {type(e).__name__}: {e}", file=sys.stderr)
    return None


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
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)

    result = data["chart"]["result"][0]
    meta = result["meta"]
    ts = result.get("timestamp") or []
    q = result["indicators"]["quote"][0]

    days, skipped = parse_bars(ts, q)
    price = meta.get("regularMarketPrice")
    if not price or not days:
        sys.exit("오류: 시세 데이터 없음")

    warnings, repaired = [], []
    if skipped:
        warnings.append(f"야후 일봉 종가 None 건너뜀: {', '.join(skipped[-5:])}")

    # 일봉에서 빠진 거래일을 5분봉 집계로 복원 (실패해도 기존 동작 유지)
    try:
        req2 = urllib.request.Request(INTRADAY_URL, headers=UA)
        with urllib.request.urlopen(req2, timeout=20) as r2:
            d2 = json.load(r2)["chart"]["result"][0]
        q2 = d2["indicators"]["quote"][0]
        idays = daily_from_intraday(d2.get("timestamp") or [], q2)
        days, repaired = merge_missing_days(days, idays)
        if repaired:
            warnings.append(f"야후 일봉 누락일 복원(5분봉 집계): {', '.join(repaired)}")
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 분봉 복원 실패: {type(e).__name__}: {e}", file=sys.stderr)

    market_date = kst_date(meta.get("regularMarketTime", 0))
    prev, prev_src, warn = pick_prev(days, market_date, tv_prev_close())
    if warn:
        warnings.append(warn)
    # 진단 로그(Actions 로그에서 확인): 최근 일봉 6개
    for d in days[-6:]:
        print("  일봉", d["date"], d["open"], d["high"], d["low"], d["close"], d["volume"],
              "(복원)" if d.get("synthetic") else "")

    payload = {
        "symbol": "000660.KS",
        "price": price,
        "previousClose": prev,
        "previousCloseSource": prev_src,
        "change": round(price - prev) if prev else None,
        "changePercent": round((price - prev) / prev * 100, 2) if prev else None,
        "marketTime": time.strftime("%Y-%m-%d %H:%M KST",
                                    time.gmtime(meta.get("regularMarketTime", 0) + 9 * 3600)),
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M KST", time.gmtime(time.time() + 9 * 3600)),
        "days": days[-2:],  # [전일, 당일] 또는 [전전일, 전일]
        "indicators": compute_indicators(days),
    }
    if repaired:
        payload["repairedDays"] = repaired
    if warnings:
        payload["warnings"] = warnings
    with open(out, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    if history_out:
        with open(history_out, "w") as f:
            json.dump(days, f)
    print(f"저장: {out} — 현재가 {price:,.0f} ({payload['changePercent']}%), 일봉 {len(days)}개")


if __name__ == "__main__":
    main()
