#!/usr/bin/env python3
"""SK하이닉스 최신 뉴스 수집기 (의존성 없음, 구글 뉴스 RSS).

사용법:
    python3 scripts/fetch_news.py [출력경로=docs/news.json] [개수=10]

구글 뉴스 RSS 검색(SK하이닉스, 최근 7일)에서 최신 기사를 수집해
제목·링크·언론사·발행일(KST)을 docs/news.json으로 저장한다.
GitHub Actions(quote.yml/charts.yml)가 리포트 주기로 실행해 커밋하고,
웹 페이지(docs/index.html)가 이 JSON을 읽어 '실시간 최신 뉴스'를
날짜와 함께 표시한다.

실패하거나 결과가 비면 비정상 종료(코드 1)해 기존 news.json을
덮어쓰지 않는다. 워크플로에서는 이 스텝을 비치명적으로 처리한다.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

# 구글 뉴스 RSS 검색 — SK하이닉스, 최근 7일, 한국어
QUERY = "SK하이닉스 when:7d"
RSS_URL = (
    "https://news.google.com/rss/search?q="
    + urllib.parse.quote(QUERY)
    + "&hl=ko&gl=KR&ceid=KR:ko"
)
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; sk-hynix-report/1.0; +https://godajava.github.io/sk-hynix-investment-report/)"


def clean_title(title):
    """구글 뉴스 제목 끝의 ' - 언론사'(또는 ' | 언론사')를 떼어 순수 제목을 얻는다."""
    src = ""
    # 마지막 ' - ' 또는 ' | ' 기준으로 언론사 접미어 분리
    for sep in (" - ", " | "):
        if sep in title:
            head, tail = title.rsplit(sep, 1)
            if 0 < len(tail) <= 20:
                title, src = head, tail
                break
    # 남은 꼬리 구분자(- | · – 등) 제거
    title = re.sub(r"\s*[|\-–·]+\s*$", "", title).strip()
    return title, src.strip()


def parse_rss(xml_bytes):
    root = ET.fromstring(xml_bytes)
    ns = {"": ""}  # 기본 네임스페이스 없음(RSS 2.0)
    items = []
    for it in root.iterfind(".//item"):
        title_raw = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        # <source> 태그(언론사) 우선, 없으면 제목 접미어에서 추출
        src_el = it.find("source")
        source = (src_el.text.strip() if src_el is not None and src_el.text else "")
        title, suffix_src = clean_title(title_raw)
        if not source:
            source = suffix_src
        if not title or not link:
            continue
        # 발행일 → KST
        date_str, dt_str, sort_key = "", "", ""
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_kst = dt.astimezone(KST)
                date_str = dt_kst.strftime("%Y-%m-%d")
                dt_str = dt_kst.strftime("%Y-%m-%d %H:%M KST")
                sort_key = dt_kst.isoformat()
            except Exception:
                pass
        items.append({
            "title": title,
            "url": link,
            "source": source,
            "date": date_str,
            "datetime": dt_str,
            "signal": classify(title),
            "_sort": sort_key,
        })
    return items


def dedup(items):
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\s+", "", it["title"])[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# 제목 키워드 기반 신호등 자동 분류(참고용) — 호재🟢 / 악재🔴 / 중립⚪
POS_KEYWORDS = (
    "상승", "급등", "강세", "신고가", "최고가", "돌파", "반등", "회복", "호재",
    "목표가 상향", "상향", "매수", "수주", "역대 최대", "최대 실적", "사상 최대",
    "흑자", "개선", "성장", "수혜", "공급", "양산", "낙관", "기대", "톱", "1위",
    "1대주주", "최대주주", "인수", "확대", "증가", "훈풍", "질주", "랠리",
)
NEG_KEYWORDS = (
    "하락", "급락", "약세", "신저가", "최저가", "이탈", "붕괴", "악재", "우려",
    "목표가 하향", "하향", "매도", "손실", "적자", "감소", "축소", "부진", "경쟁",
    "리스크", "위기", "차질", "둔화", "경고", "규제", "제재", "소송", "조사",
    "중단", "철수", "쇼크", "패닉", "폭락", "논란", "위험", "불안", "타격",
)


def classify(title):
    """제목 키워드로 신호등(호재/악재/중립)을 자동 분류한다."""
    pos = sum(1 for k in POS_KEYWORDS if k in title)
    neg = sum(1 for k in NEG_KEYWORDS if k in title)
    if pos > neg:
        return {"cls": "up", "label": "호재", "emoji": "🟢"}
    if neg > pos:
        return {"cls": "down", "label": "악재", "emoji": "🔴"}
    return {"cls": "flat", "label": "중립", "emoji": "⚪"}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "docs/news.json"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    req = urllib.request.Request(RSS_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        xml_bytes = r.read()

    items = parse_rss(xml_bytes)
    items = dedup(items)
    # 최신순 정렬(발행일 있는 항목 우선)
    items.sort(key=lambda x: x["_sort"], reverse=True)
    items = items[:limit]
    for it in items:
        it.pop("_sort", None)

    if not items:
        sys.exit("오류: 수집된 뉴스가 없음 — 기존 news.json 유지")

    data = {
        "fetchedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "query": QUERY,
        "source": "Google News RSS",
        "items": items,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"생성: {out_path} — 뉴스 {len(items)}건 (최신 {items[0]['date']} ~)")


if __name__ == "__main__":
    main()
