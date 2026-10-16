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


# 같은 사안을 다른 언론사가 다른 제목으로 보도하면(예: "노사, 임단협 수정안
# 마련…현금 50%" vs "성과급 절반 현금으로…노사 수정안 마련") 위 dedup()의
# 정확 일치 방식으로는 걸러지지 않는다. 제목을 글자 2-gram 집합으로 바꿔
# 겹침 비율을 비교하는 방식은 조사(은/는/을/를 등)가 붙어 단어가 달라져도
# 흔들리지 않고, 형태소 분석기 등 외부 의존성도 필요 없다.
_TOPIC_STRIP = re.compile(r"SK하이닉스|하이닉스")
_NON_KO_NUM = re.compile(r"[^가-힣0-9]")


def _bigrams(title):
    s = _NON_KO_NUM.sub("", _TOPIC_STRIP.sub("", title))
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


# 같은 사건을 다른 각도·다른 표현으로 쓴 기사(예: 10/13 급락 당일에만 "10% 폭락 마감",
# "140만닉스 후퇴", "144만원 붕괴", "검은 화요일", "매도 사이드카" 등 15건 이상)는
# 2-gram 겹침만으로는 잘 안 걸러진다. 그래서 제목에서 읽히는 '사안(주제) 태그'를
# 먼저 부여하고, 같은 태그가 48시간 이내에 이미 채택돼 있으면 중복으로 본다.
# 규칙은 위에서부터 첫 매치가 이기므로 구체적인 사안을 앞에 둔다
# (예: "CXMT 쇼크…급락"은 'crash'가 아니라 'cxmt'로 묶여야 한다).
TOPIC_RULES = (
    ("keynote", r"안현|HBF|3D\s?D램|메모리 계층|AI 인프라|병목|SEDEX"),
    ("recruit", r"구직자|취준생|취업|관심기업|채용"),
    ("history", r"43년|초심"),
    ("cxmt", r"CXMT|창신|[中중]국(발)?\s?(반도체|메모리|D램|기술)|中\s?(반도체|메모리|D램)"),
    ("leverage_etf", r"레버리지|인버스|ETF"),
    ("target_price", r"목표가|목표주가|리포트 브리핑|증권가"),
    ("earnings", r"영업이익|영업익|실적 전망|컨센서스|어닝|\d분기 실적|실적 발표|이익률"),
    ("solidigm", r"솔리다임"),
    ("adr", r"ADR|美 상장|미국 상장|락업"),
    ("treasury", r"자사주|주주환원|배당"),
    ("us_invest", r"R&D|연구동맹|EPIC|에픽|기공식|주지사|美\s?\d+조|미국 제조업"),
    ("hbm_equipment", r"후공정|장비"),
    ("expo", r"반도체대전"),
    ("labor", r"노조|성과급|임단협|파업|노사"),
    ("export", r"수출"),
    ("crash", r"급락|폭락|곤두박질|추락|반토막|검은 화요일|사이드카|서킷브레이커|하락 마감|마감시황|10%대|붕괴"),
    ("market_wrap", r"마감시황|증시\s?(마감|개장)|코스(피|닥).{0,12}(마감|출발)|시황"),
)
_TOPIC_RE = tuple((tag, re.compile(rx)) for tag, rx in TOPIC_RULES)
# 정보량이 거의 없는 사진 캡션성 기사는 아예 제외한다.
LOW_INFO = re.compile(r"^\s*\[(포토|사진|영상|화보|동영상)\]")
TOPIC_WINDOW_HOURS = 48


def topic_tag(title):
    for tag, rx in _TOPIC_RE:
        if rx.search(title):
            return tag
    return None


def _hours_apart(a, b):
    """_sort(ISO 문자열) 두 개의 시간 차(시간). 파싱 불가면 0(=같은 시기로 간주)."""
    try:
        return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) / 3600
    except Exception:
        return 0.0


def dedup_topic(items, threshold=0.35):
    """같은 사안을 다룬 기사가 여럿이면 가장 최신 1건만 남긴다.
    1) 사진 캡션성 기사 제외
    2) 사안 태그가 같고 48시간 이내면 중복
    3) 제목 2-gram 겹침(threshold 이상)이면 중복
    호출 전 items는 최신순으로 정렬돼 있어야 한다(각 클러스터의 대표로
    가장 최근 기사가 남도록)."""
    kept, kept_bg, kept_tag = [], [], []
    for it in items:
        if LOW_INFO.search(it["title"]):
            continue
        tag = topic_tag(it["title"])
        bg = _bigrams(it["title"])
        dup = False
        for k, prev_bg, prev_tag in zip(kept, kept_bg, kept_tag):
            near = _hours_apart(it.get("_sort", ""), k.get("_sort", "")) <= TOPIC_WINDOW_HOURS
            if tag and prev_tag == tag and near:
                dup = True
                break
            if len(bg & prev_bg) / min(len(bg), len(prev_bg)) >= threshold:
                dup = True
                break
        if dup:
            continue
        kept.append(it)
        kept_bg.append(bg)
        kept_tag.append(tag)
    return kept


# 제목 키워드 기반 신호등 자동 분류(참고용) — 호재🟢 / 악재🔴 / 중립⚪
#
# 3단계로 판정한다:
#  1) PHRASE_RULES — 의미가 방향 반전될 수 있는 복합 표현을 문구 단위로 먼저 검사.
#     예) "1위 자리 내줘"(주체가 밀려남 → 악재)는 "1위"만 보면 호재로 오판되므로
#     단일 키워드보다 먼저 검사해 우선 적용한다. 매치되면 즉시 확정.
#  2) RESOLUTION_SUFFIXES — 악재 키워드라도 뒤에 "해소/완화/진정" 등이 붙으면
#     (예: "공급부족 우려 해소") 그 우려가 해결됐다는 뜻이므로 악재 카운트에서 뺀다.
#  3) 나머지는 키워드 카운트(합계 비교)로 판정 — 동률이면 중립.
#
# 방향이 문맥에 따라 뒤집히는 단일 키워드(확대/증가/축소/감소/경쟁/공급/1위 등)는
# 목록에서 제거하고, 안전하게 방향이 고정되는 복합 표현만 PHRASE_RULES에 남긴다.
POS_PHRASES = (
    "역대 최대", "최대 실적", "사상 최대", "흑자 전환", "목표가 상향", "목표주가 상향",
    "실적 상향", "점유율 확대", "매출 확대", "수주 확대", "투자 확대", "생산 확대",
    "출하 확대", "공급부족", "공급 부족", "품귀", "1위 탈환", "1위 굳히기", "1위 수성",
    "경쟁력 강화", "경쟁 우위",
    # 승소/서프라이즈 계열 — "소송"(악재 키워드)·"기대"(호재 키워드) 등과 결합돼도
    # 방향이 뒤집히지 않도록 문구 단위로 먼저 확정한다.
    "승소", "어닝서프라이즈", "실적 서프라이즈", "깜짝 실적", "예상 상회", "기대 상회",
    "컨센서스 상회", "눈높이 상회",
)
NEG_PHRASES = (
    "적자 전환", "적자 확대", "손실 확대", "목표가 하향", "목표주가 하향", "목표가 인하",
    "목표주가 인하", "실적 하향", "실적 눈높이", "점유율 축소", "점유율 하락",
    "매출 감소", "이익 감소", "생산 축소", "감산", "투자 축소", "공급 과잉", "과잉 공급",
    "1위 자리 내줘", "1위 뺏겨", "1위 내주", "경쟁 심화", "경쟁 격화",
    # 패소/어닝쇼크/기대 이하 계열 — "기대"(호재 키워드)가 함께 있어도 상쇄되지
    # 않도록 문구 단위로 먼저 확정한다.
    "패소", "어닝쇼크", "실적쇼크", "실적 쇼크", "기대 이하", "기대이하", "기대 밑돌",
    "예상 하회", "예상하회", "기대 하회", "기대하회", "컨센서스 하회", "눈높이 하회",
)
POS_KEYWORDS = (
    "상승", "급등", "강세", "신고가", "최고가", "돌파", "반등", "회복", "호재",
    "상향", "매수", "수주", "흑자", "개선", "성장", "수혜", "양산", "낙관",
    "기대", "톱", "인수", "훈풍", "질주", "랠리",
)
NEG_KEYWORDS = (
    "하락", "급락", "약세", "신저가", "최저가", "이탈", "붕괴", "악재", "우려",
    "하향", "매도", "손실", "적자", "부진", "리스크", "위기", "차질", "둔화",
    "경고", "규제", "제재", "소송", "조사", "중단", "철수", "쇼크", "패닉",
    "폭락", "논란", "위험", "불안", "타격",
)
# 악재 키워드 뒤에 이런 표현이 붙으면 "그 우려/위기가 해소됐다"는 뜻이므로
# 악재 카운트에서 제외한다. 예: "공급부족 우려 해소", "규제 리스크 완화"
RESOLUTION_SUFFIXES = ("해소", "완화", "진정", "종식", "극복", "누그러")


def _strip_resolved_negatives(title, neg_hits):
    """뒤에 해소/완화 등이 붙어 반전된 악재 키워드를 카운트에서 제외한다."""
    resolved = 0
    for kw in neg_hits:
        idx = title.find(kw)
        if idx == -1:
            continue
        tail = title[idx + len(kw): idx + len(kw) + 6]
        if any(suf in tail for suf in RESOLUTION_SUFFIXES):
            resolved += 1
    return resolved


def classify(title):
    """제목을 신호등(호재/악재/중립)으로 자동 분류한다. PHRASE_RULES 우선,
    그 다음 해소 표현 반영 키워드 카운트 순으로 판정한다."""
    for p in POS_PHRASES:
        if p in title:
            return {"cls": "up", "label": "호재", "emoji": "🟢"}
    for p in NEG_PHRASES:
        if p in title:
            return {"cls": "down", "label": "악재", "emoji": "🔴"}

    pos_hits = [k for k in POS_KEYWORDS if k in title]
    neg_hits = [k for k in NEG_KEYWORDS if k in title]
    pos = len(pos_hits)
    neg = len(neg_hits) - _strip_resolved_negatives(title, neg_hits)

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
    raw_count = len(items)
    items = dedup(items)
    # 최신순 정렬(발행일 있는 항목 우선) 후 같은 주제 기사는 최신 1건만 남긴다.
    # limit으로 자르기 전에 전체 수집분을 대상으로 주제 중복을 제거하므로,
    # 제거된 만큼 원본 풀에 남아있는 다른(중복 아닌) 기사로 자연히 채워진다 —
    # 원본 풀 자체가 부족할 때만(최근 7일간 보도가 적을 때) limit보다 적게 나온다.
    items.sort(key=lambda x: x["_sort"], reverse=True)
    items = dedup_topic(items)
    topic_unique_count = len(items)
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
    print(
        f"생성: {out_path} — 뉴스 {len(items)}건(요청 {limit}건, 원본 {raw_count}건 → "
        f"주제 중복 제거 후 {topic_unique_count}건) (최신 {items[0]['date']} ~)"
    )
    if topic_unique_count < limit:
        print(f"참고: 최근 7일 보도에서 서로 다른 주제가 {topic_unique_count}건뿐이라 {limit}건을 채우지 못함")


if __name__ == "__main__":
    main()
