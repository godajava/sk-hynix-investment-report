#!/usr/bin/env python3
"""코스피200 야간선물 수집 후보 소스 탐색(임시, 3차)."""
import json, re, time, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/json,text/html,*/*", "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}

def call(url, data=None, headers=None):
    h = dict(UA); h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body: h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")
    except Exception as e:
        return 0, f"ERR {type(e).__name__}: {e}"

def show(name, st, body, n=1800):
    print(f"== {name} | HTTP {st} | {len(body)}B | {re.sub(chr(10), ' ', body)[:n]}")

COLS = ["name", "description", "close", "change", "change_abs", "open", "high", "low", "volume", "update_mode", "exchange", "type", "currency"]
for mkt in ("futures", "global", "korea"):
    st, b = call(f"https://scanner.tradingview.com/{mkt}/scan",
                 {"symbols": {"tickers": ["KRX:K2I1!", "KRX:K2I2!", "KRX:K200", "KRX:KOSPI200"]}, "columns": COLS})
    show(f"tv-scan-{mkt}", st, b)
st, b = call("https://symbol-search.tradingview.com/symbol_search/v3/?text=KOSPI%20200%20futures&hl=1&lang=en&search_type=futures",
             headers={"Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"})
show("tv-symbol-search", st, b, 2500)

# 네이버: 해외 지수/종목 코드 탐색
for nm, u in [
    ("naver-ac-skhynix-adr", "https://ac.stock.naver.com/ac?q=SK%ED%95%98%EC%9D%B4%EB%8B%89%EC%8A%A4&target=index,stock"),
    ("naver-ac-sox", "https://ac.stock.naver.com/ac?q=SOX&target=index,stock"),
    ("naver-world-sox-a", "https://api.stock.naver.com/index/.SOX/basic"),
    ("naver-world-sox-b", "https://m.stock.naver.com/api/index/.SOX/basic"),
    ("naver-world-ixic", "https://api.stock.naver.com/index/.IXIC/basic"),
]:
    st, b = call(u, headers={"Referer": "https://m.stock.naver.com/"}); show(nm, st, b, 900)

# 다음: Referer 지정
for nm, u in [
    ("daum-fut-a", "https://finance.daum.net/api/quotes/FUT"),
    ("daum-search", "https://finance.daum.net/api/search/ranks?limit=3"),
]:
    st, b = call(u, headers={"Referer": "https://finance.daum.net/"}); show(nm, st, b, 500)

# 야후: 느리게 호출(429 회피)
for nm, sym in [("SOX", "%5ESOX"), ("EWY", "EWY"), ("SKHY", "SKHY")]:
    time.sleep(4)
    st, b = call(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d")
    show("yahoo-" + nm, st, b, 500)
