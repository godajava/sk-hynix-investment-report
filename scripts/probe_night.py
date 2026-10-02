#!/usr/bin/env python3
"""코스피200 야간선물 수집 후보 소스 탐색(임시). 상태코드·길이·스니펫만 출력한다."""
import json, re, sys, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/json,text/html,*/*", "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}

CANDS = [
    ("naver-m-FUT-basic", "https://m.stock.naver.com/api/index/FUT/basic"),
    ("naver-polling-FUT", "https://polling.finance.naver.com/api/realtime/domestic/index/FUT"),
    ("naver-m-FUT-price", "https://m.stock.naver.com/api/index/FUT/price?pageSize=3&page=1"),
    ("naver-m-FUT-integration", "https://m.stock.naver.com/api/index/FUT/integration"),
    ("naver-m-FUTN-basic", "https://m.stock.naver.com/api/index/FUTN/basic"),
    ("naver-m-NFUT-basic", "https://m.stock.naver.com/api/index/NFUT/basic"),
    ("cnbc-ks200", "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=.KS200&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1"),
    ("yahoo2-SOX", "https://query2.finance.yahoo.com/v8/finance/chart/%5ESOX?range=5d&interval=1d"),
]

def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")
    except Exception as e:
        return 0, f"ERR {type(e).__name__}: {e}"

for name, url in CANDS:
    st, body = get(url)
    snip = re.sub(r"\s+", " ", body)[:3500]
    print(f"== {name} | HTTP {st} | {len(body)}B | {snip}")
    if name.startswith("yahoo-search"):
        try:
            for q in json.loads(body).get("quotes", []):
                print("   ·", q.get("symbol"), "|", q.get("shortname") or q.get("longname"), "|", q.get("exchDisp"), "|", q.get("quoteType"))
        except Exception as e:
            print("   (parse fail)", e)
    # 야간/선물 키워드 근처 스니펫
    for m in list(re.finditer(r"야간|night|Night", body))[:3]:
        a = max(0, m.start() - 60); print("   ~", re.sub(r"\s+", " ", body[a:m.start() + 160]))
