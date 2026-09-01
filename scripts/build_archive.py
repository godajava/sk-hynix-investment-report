#!/usr/bin/env python3
"""과거 리포트 아카이브 페이지 생성기.

reports/sk-hynix/YYYY-MM-DD.md 전체를 훑어 날짜·유형·종가·등락·판정을 뽑아
docs/archive.html(정적 인덱스)을 만든다. 실제 본문은 GitHub의 해당 .md로 링크한다
(리포트별 HTML 스냅샷은 보관하지 않으므로).

사용법: python3 scripts/build_archive.py
"""
import glob
import os
import re
import datetime

REPO_BLOB = "https://github.com/godajava/sk-hynix-investment-report/blob/main/reports/sk-hynix"
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def parse_report(path, date):
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    title = lines[0] if lines else ""

    # 유형: 제목의 마지막 "—" 뒤 부분에서 뽑는다. 새 형식이 아니면 빈 문자열.
    kind = ""
    m = re.search(r"—\s*\d{4}-\d{2}-\d{2}\s*\([월화수목금토일]\)\s*(.+)$", title)
    if m:
        kind = m.group(1).strip()

    # 종가·등락·판정은 "> **작성** ..." 요약 줄 하나에서만 뽑는다(8/7 이전 구형
    # 파일은 이 줄이 없어 본문 중 엉뚱한 숫자를 집을 수 있으므로 아예 건너뛴다).
    price = ""
    pct = ""
    verdict = ""
    summary = re.search(r"^>\s*\*\*작성\*\*.*$", text, re.MULTILINE)
    if summary:
        line = summary.group(0)
        for kw in ["매도 재전환 확정", "매수 전환 확정", "매도 → 중립 복귀 확정",
                   "매수 → 중립", "중립 유지", "매수 유지", "매도 유지"]:
            if kw in line:
                verdict = kw
                break
        mp = re.search(r"(\d[\d,]*\.?\d*만)", line)
        if mp:
            price = mp.group(1)
        mc = re.search(r"([+\-−]\d+\.\d+)%", line)
        if mc:
            pct = mc.group(1).replace("−", "-") + "%"

    weekday = WEEKDAY_KO[date.weekday()]
    return {
        "date": date.strftime("%Y-%m-%d"),
        "weekday": weekday,
        "kind": kind or "—",
        "price": price,
        "pct": pct,
        "verdict": verdict or "—",
    }


def build():
    files = sorted(glob.glob("reports/sk-hynix/*.md"))
    rows = []
    for path in files:
        base = os.path.basename(path)
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\.md$", base)
        if not m:
            continue
        date = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        rows.append(parse_report(path, date))
    rows.sort(key=lambda r: r["date"], reverse=True)

    def verdict_class(v):
        if "매도" in v and "복귀" not in v and "중립" not in v:
            return "v-sell"
        if "매수" in v and "중립" not in v:
            return "v-buy"
        if "중립" in v:
            return "v-neutral"
        return ""

    tr = []
    for r in rows:
        pct_html = ""
        if r["pct"]:
            cls = "up" if r["pct"].startswith("+") else "down"
            pct_html = f'<span class="pct {cls}">{r["pct"]}</span>'
        tr.append(
            "<tr>"
            f'<td class="num">{r["date"]} ({r["weekday"]})</td>'
            f'<td>{r["kind"]}</td>'
            f'<td class="num">{r["price"]} {pct_html}</td>'
            f'<td><span class="badge {verdict_class(r["verdict"])}">{r["verdict"]}</span></td>'
            f'<td><a href="{REPO_BLOB}/{r["date"]}.md" target="_blank" rel="noopener">원문 ↗</a></td>'
            "</tr>"
        )

    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>지난 리포트 — SK하이닉스 투자 리포트</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f4f5f7; --paper: #ffffff; --ink: #16181d; --ink-2: #4a4c52; --muted: #74767c;
  --hairline: #e6e7ea; --hairline-strong: #cfd1d6; --accent: #2a6fd0;
  --up: #d64545; --down: #2a78d6; --neutral: #a6790a; --neutral-bg: rgba(120,120,124,0.12);
  --sell-bg: rgba(214,69,69,0.10); --buy-bg: rgba(31,157,99,0.12); --buy: #1f9d63;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg: #15171c; --paper: #1b1d23; --ink: #e8e9ec; --ink-2: #b6b8c0; --muted: #888b93;
    --hairline: #2b2e36; --hairline-strong: #3c3f49; --accent: #6ea8ff;
    --up: #ff6b6b; --down: #6ea8ff; --neutral: #e3b34d; --neutral-bg: rgba(227,179,77,0.14);
    --sell-bg: rgba(255,107,107,0.14); --buy-bg: rgba(74,211,147,0.14); --buy: #4ad393;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg: #15171c; --paper: #1b1d23; --ink: #e8e9ec; --ink-2: #b6b8c0; --muted: #888b93;
  --hairline: #2b2e36; --hairline-strong: #3c3f49; --accent: #6ea8ff;
  --up: #ff6b6b; --down: #6ea8ff; --neutral: #e3b34d; --neutral-bg: rgba(227,179,77,0.14);
  --sell-bg: rgba(255,107,107,0.14); --buy-bg: rgba(74,211,147,0.14); --buy: #4ad393;
}}
body {{
  background: var(--bg); color: var(--ink); margin: 0;
  font-family: "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif;
  font-size: 15px; line-height: 1.7;
}}
.sheet {{ max-width: 880px; margin: 0 auto; padding: 40px 20px 72px; }}
.paper {{ background: var(--paper); border: 1px solid var(--hairline); border-top: 3px solid var(--accent); padding: 36px 40px 48px; }}
@media (max-width: 640px) {{ .paper {{ padding: 24px 16px 32px; }} }}
h1 {{ font-size: 22px; font-weight: 800; margin: 0 0 6px; }}
.sub {{ font-size: 13px; color: var(--muted); margin: 0 0 28px; }}
.sub a {{ color: var(--accent); text-decoration: none; }}
.tablewrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
th {{ text-align: left; font-size: 12px; letter-spacing: 0.04em; color: var(--muted); font-weight: 600;
  padding: 8px 12px; border-bottom: 1px solid var(--hairline-strong); white-space: nowrap; }}
td {{ padding: 9px 12px; border-bottom: 1px solid var(--hairline); vertical-align: top; }}
td.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
td a {{ color: var(--accent); text-decoration: none; }}
td a:hover {{ text-decoration: underline; }}
.pct {{ margin-left: 6px; font-weight: 700; }}
.pct.up {{ color: var(--up); }}
.pct.down {{ color: var(--down); }}
.badge {{ font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 3px; background: var(--neutral-bg); color: var(--neutral); white-space: nowrap; }}
.badge.v-buy {{ background: var(--buy-bg); color: var(--buy); }}
.badge.v-sell {{ background: var(--sell-bg); color: var(--up); }}
footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--hairline-strong); font-size: 12px; color: var(--muted); }}
</style>
<script>
(function () {{
  try {{
    var t = localStorage.getItem("sk-hynix-theme");
    if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  }} catch (e) {{}}
}})();
</script>
</head><body>
<div class="sheet"><div class="paper">
<h1>지난 리포트</h1>
<p class="sub">SK하이닉스(KRX 000660) 일별 리포트 목록입니다 · <a href="https://godajava.github.io/sk-hynix-investment-report/">오늘 리포트로 돌아가기 ↗</a></p>
<div class="tablewrap">
<table>
<tr><th>날짜</th><th>유형</th><th>종가/등락</th><th>판정</th><th>원문</th></tr>
{"".join(tr)}
</table>
</div>
<footer>본 목록은 각 날짜 리포트 파일(.md)에서 자동 추출한 요약이며 표기가 부정확할 수 있습니다. 정확한 내용은 원문 링크를 확인하세요.</footer>
</div></div>
</body></html>"""

    os.makedirs("docs", exist_ok=True)
    open("docs/archive.html", "w", encoding="utf-8").write(html)
    print(f"생성: docs/archive.html ({len(rows)}건, {len(html):,} bytes)")


if __name__ == "__main__":
    build()
