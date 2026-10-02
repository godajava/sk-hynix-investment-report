#!/usr/bin/env python3
"""프리마켓 프리뷰용 스냅샷 수집기 (의존성 없음).

사용법:
    python3 scripts/fetch_night.py [출력경로=docs/night_futures.json] [--print]

수집 항목
  - 코스피200 선물 연속월물(트레이딩뷰 스캐너 KRX:K2I1!). 08:45 이후엔 주간 실시간 값이므로
    night_futures_valid=false. 06:00~08:44 사이 수집분만 야간선물로 본다(첫 실측으로 검증 필요)
  - 코스피200 주간 선물 종가(네이버 FUT) · 코스피200 현물지수
  - 미국 지수/반도체(트레이딩뷰·네이버): SOX, 나스닥, S&P500, 마이크론, 엔비디아, EWY, 원/달러
GitHub Actions(night.yml)가 평일 아침에 실행해 docs/night_futures.json을 커밋하고,
프리마켓 브리핑은 git pull 후 이 파일을 읽는다(파일 수정 없음).
소스 하나가 실패해도 나머지는 저장하고, 필드별 오류는 errors에 남긴다.
"""
import json, sys, time, datetime, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/json,*/*", "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}
KST = datetime.timezone(datetime.timedelta(hours=9))
COLS = ["name", "description", "close", "change", "change_abs", "open", "high", "low", "volume", "update_mode"]
EXTRA_COLS = ["update_time", "last_bar_update_time"]  # 있을 때만 (실패해도 무시)


def http(url, data=None, headers=None, tries=3):
    h = dict(UA); h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body:
        h["Content-Type"] = "application/json"
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {type(last).__name__}: {last}")


def tv_scan(tickers, cols=COLS):
    """트레이딩뷰 스캐너 → {ticker: {col: value}}"""
    res = http("https://scanner.tradingview.com/global/scan",
               {"symbols": {"tickers": tickers}, "columns": cols})
    out = {}
    for row in res.get("data", []):
        out[row["s"]] = dict(zip(cols, row["d"]))
    return out


def num(x, nd=2):
    return None if x is None else round(float(x), nd)


def pack(d, nd=2):
    if not d:
        return None
    return {
        "name": d.get("description") or d.get("name"),
        "last": num(d.get("close"), nd), "changePct": num(d.get("change"), 2),
        "change": num(d.get("change_abs"), nd), "open": num(d.get("open"), nd),
        "high": num(d.get("high"), nd), "low": num(d.get("low"), nd),
        "volume": d.get("volume"), "mode": d.get("update_mode"),
        **({"updateTime": d["update_time"],
            "updateTimeKST": datetime.datetime.fromtimestamp(d["update_time"], KST).strftime("%m-%d %H:%M:%S")}
           if d.get("update_time") else {}),
    }


# 슬롯 → 트레이딩뷰 후보 티커(앞에서부터 데이터가 있는 첫 번째를 사용)
SLOTS = {
    "night_futures": ["KRX:K2I1!"],
    "night_futures_next": ["KRX:K2I2!"],
    "kospi200_cash": ["KRX:KOSPI200"],
    "sox": ["NASDAQ:SOX", "TVC:SOX", "SP:SOX"],
    "nasdaq": ["NASDAQ:IXIC", "TVC:IXIC"],
    "sp500": ["SP:SPX", "TVC:SPX"],
    "micron": ["NASDAQ:MU"],
    "nvidia": ["NASDAQ:NVDA"],
    "ewy": ["AMEX:EWY", "NYSE:EWY", "ARCA:EWY"],
    "usdkrw": ["FX_IDC:USDKRW", "FX:USDKRW"],
    "sk_hynix": ["KRX:000660"],
    "samsung": ["KRX:005930"],
    "hynix_adr": ["NASDAQ:SKHY", "NYSE:SKHY", "AMEX:SKHY", "NYSEARCA:SKHY", "NASDAQ:SKHYV", "NYSE:SKHYV"],
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_path = args[0] if args else "docs/night_futures.json"
    errors, snap = {}, {}

    alltk = sorted({t for v in SLOTS.values() for t in v})
    try:
        try:
            raw = tv_scan(alltk, COLS + EXTRA_COLS)
        except Exception as e:  # 추가 컬럼 미지원 시 기본 컬럼으로 재시도
            errors["tv_extra_cols"] = str(e)
            raw = tv_scan(alltk, COLS)
    except Exception as e:  # noqa: BLE001
        raw = {}
        errors["tradingview"] = str(e)

    for slot, cands in SLOTS.items():
        hit = next((t for t in cands if raw.get(t) and raw[t].get("close") is not None), None)
        if hit:
            snap[slot] = {"symbol": hit, **pack(raw[hit], 4 if slot == "usdkrw" else 2)}
        else:
            snap[slot] = None
            errors[slot] = f"no data from {cands}"

    # 네이버: 코스피200 주간 선물(직전 주간 종가), 해외지수 SOX/나스닥 종가(교차 검증)
    try:
        fut = http("https://m.stock.naver.com/api/index/FUT/basic", headers={"Referer": "https://m.stock.naver.com/"})
        snap["day_futures_naver"] = {"month": fut.get("month"), "last": fut.get("closePrice"),
                                     "changePct": fut.get("fluctuationsRatio"), "status": fut.get("marketStatus"),
                                     "tradedAt": fut.get("localTradedAt")}
    except Exception as e:  # noqa: BLE001
        errors["naver_fut"] = str(e)
    for key, code in (("sox_naver", ".SOX"), ("nasdaq_naver", ".IXIC")):
        try:
            w = http(f"https://api.stock.naver.com/index/{code}/basic", headers={"Referer": "https://m.stock.naver.com/"})
            snap[key] = {"last": w.get("closePrice"), "changePct": w.get("fluctuationsRatio"),
                         "tradedAt": w.get("localTradedAt")}
        except Exception as e:  # noqa: BLE001
            errors[key] = str(e)

    if not snap.get("hynix_adr"):
        try:
            ac = http("https://ac.stock.naver.com/ac?q=SKHY&target=stock", headers={"Referer": "https://m.stock.naver.com/"})
            items = [i for i in ac.get("items", []) if i.get("nationCode") == "USA"]
            if not items:
                ac = http("https://ac.stock.naver.com/ac?q=SK%20hynix&target=stock", headers={"Referer": "https://m.stock.naver.com/"})
                items = [i for i in ac.get("items", []) if i.get("nationCode") == "USA"]
            code = items[0]["reutersCode"] if items else None
            snap["hynix_adr_naver_candidates"] = [(i.get("name"), i.get("reutersCode")) for i in items[:5]]
            if code:
                w = http(f"https://api.stock.naver.com/stock/{code}/basic", headers={"Referer": "https://m.stock.naver.com/"})
                snap["hynix_adr"] = {"symbol": code, "name": w.get("stockName"), "last": w.get("closePrice"),
                                     "changePct": w.get("fluctuationsRatio"), "tradedAt": w.get("localTradedAt"), "source": "naver"}
                errors.pop("hynix_adr", None)
        except Exception as e:  # noqa: BLE001
            errors["hynix_adr_naver"] = str(e)

    # 야간선물 유효성: 08:45(주간 개장)~15:45 사이에 찍은 K2I1!은 주간 정규장 실시간 값이라 야간선물이 아니다.
    now = datetime.datetime.now(KST)
    hm = now.hour * 60 + now.minute
    day_live = (8 * 60 + 45) <= hm < (15 * 60 + 50)
    snap["night_futures_valid"] = not day_live
    snap["night_futures_note"] = ("주간 정규장 시간대에 수집돼 야간선물이 아님(KRX:K2I1!은 주간 실시간 값)"
                                  if day_live else
                                  "개장 전/야간 시간대 수집 — 마지막 세션(야간 포함 여부는 첫 실측으로 검증 필요) 값")
    nf, dn = snap.get("night_futures"), snap.get("day_futures_naver")
    if nf and dn and dn.get("last") and not day_live:
        try:
            day_close = float(str(dn["last"]).replace(",", ""))
            snap["night_vs_day_close_pct"] = round((nf["last"] / day_close - 1) * 100, 2)
        except Exception as e:  # noqa: BLE001
            errors["night_vs_day"] = str(e)

    result = {
        "fetchedAt": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "note": "night_futures=KRX:K2I1!(트레이딩뷰, 20분 지연). 야간 세션(18:00~익일 06:00) 종료 후에는 야간 종가에 해당. 근사 지표이며 투자 판단은 종가 기준.",
        **snap, "errors": errors,
    }
    if "--print" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if "--no-write" not in sys.argv:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    if not snap.get("night_futures"):
        sys.exit(1)  # 핵심 항목 없으면 비정상 종료(기존 파일 유지)


if __name__ == "__main__":
    main()
