#!/usr/bin/env python3
"""'주간 변동 원인 분석' 섹션 렌더러.

docs/cause_analysis.json(매 사이클 갱신하는 큐레이션 데이터)을 읽어
  - scripts/report_template.html 의 <!--CAUSE:START-->…<!--CAUSE:END--> 구간
  - reports/sk-hynix/<date>.md 의 <!--CAUSE:START-->…<!--CAUSE:END--> 구간
을 다시 쓴다. 마커가 없으면 템플릿은 '02 주가 동향' 섹션 앞, md는 '## 시세' 앞에 삽입한다.

사용법: python3 scripts/cause_block.py <YYYY-MM-DD>   (이후 build_web.py·build_archive.py 실행)
"""
import sys, json, html, re

S, E = "<!--CAUSE:START-->", "<!--CAUSE:END-->"
e = html.escape


def fnum(v, nd=2):
    return "—" if v is None else f"{v:+.{nd}f}%"


def cnum(v):
    if v is None:
        return "—"
    col = "var(--up)" if v > 0 else ("var(--down)" if v < 0 else "var(--ink-2)")
    return f'<span style="color:{col}">{v:+.2f}%</span>'


def render_html(d):
    o = [S, "<section>",
         f'<h2><span class="no">WHY</span>주간 변동 원인 분석 — 국내·해외·미국 빅테크 '
         f'<small style="font-size:12px;font-weight:500;color:var(--muted)">{e(d["week"])} · 기준 {e(d["asof"])}</small></h2>',
         f'<p><strong>한 줄 결론</strong> — {e(d["headline"])}</p>',
         f'<p style="color:var(--muted);font-size:12px">{e(d["method_note"])}</p>',
         '<p><strong>① 시장 현황 — 한국·미국 지수와 빅테크</strong></p>',
         '<div class="tablewrap"><table class="kv why"><colgroup><col style="width:34%"><col style="width:24%"><col style="width:20%"><col style="width:22%"></colgroup>',
         '<tr><th>종목·지수</th>' + ''.join(f'<th>{e(c)}</th>' for c in d.get('cols',['11/5(목)','11/6(금)','주간'])) + '</tr>']
    for g in d["table"]:
        o.append(f'<tr><th colspan="4" style="text-align:left">{e(g["group"])}</th></tr>')
        for r in g["rows"]:
            nm, d5, d6, wk = r[0], r[1], r[2], r[3]
            d5s = e(d5) if isinstance(d5, str) else cnum(d5)
            c5 = '<td style="text-align:right;font-size:11px">' + d5s + '</td>' if isinstance(d5, str) else '<td class="num">' + d5s + '</td>'
            o.append(f'<tr><td>{e(nm)}</td>{c5}<td class="num">{cnum(d6)}</td><td class="num">{cnum(wk)}</td></tr>')
    o += ['</table></div>', f'<p style="color:var(--muted);font-size:12px">{e(d["table_note"])}</p>',
          '<p><strong>② 원인 사슬 — 시간순</strong></p>',
          '<div class="tablewrap"><table class="kv why"><colgroup><col style="width:21%"><col style="width:49%"><col style="width:30%"></colgroup><tr><th>시점</th><th>사건·수치</th><th>확신·출처</th></tr>']
    for c in d["chain"]:
        o.append(f'<tr><td>{e(c["when"])}</td><td>{e(c["fact"])}</td><td>{e(c["conf"])}</td></tr>')
    o += ['</table></div>', '<p><strong>③ 원인 순위 — 무엇이 얼마나 확실한가</strong></p>',
          '<div class="tablewrap"><table class="kv why"><colgroup><col style="width:8%"><col style="width:24%"><col style="width:46%"><col style="width:22%"></colgroup><tr><th>순위</th><th>원인</th><th>근거</th><th>확신</th></tr>']
    for i, c in enumerate(d["causes"], 1):
        o.append(f'<tr><td class="num">{i}</td><td>{e(c["title"])}</td><td>{e(c["evidence"])}</td><td>{e(c["conf"])}</td></tr>')
    o += ['</table></div>', '<p><strong>④ 분석 판단 (추정 포함)</strong></p><ul>']
    o += [f'<li>{e(x)}</li>' for x in d["judgement"]]
    o += ['</ul>', '<p><strong>⑤ 아직 모르는 것과 반증 조건</strong></p><ul>']
    o += [f'<li>{e(x)}</li>' for x in d["unknown"]]
    o += ['</ul>', f'<p><strong>⑥ 다음 거래일 시사점</strong> — {e(d["outlook"])}</p>',
          '<p style="color:var(--muted);font-size:12px">출처(검색 요약 기준, 일부 원문 미열람): ' +
          ' · '.join(f'<a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["title"])}</a>' for s in d["sources"]) + '</p>',
          "</section>", E]
    return "\n".join(o)


def render_md(d):
    o = [S, f'## 주간 변동 원인 분석 — 국내·해외·미국 빅테크 ({d["week"]}, 기준 {d["asof"]})', "",
         f'**한 줄 결론** — {d["headline"]}', "", f'> {d["method_note"]}', "",
         "**① 시장 현황**", "", "| 종목·지수 | " + " | ".join(d.get("cols",["11/5(목)","11/6(금)","주간"])) + " |", "|---|---|---|---|"]
    for g in d["table"]:
        o.append(f'| **{g["group"]}** | | | |')
        for r in g["rows"]:
            d5 = r[1] if isinstance(r[1], str) else fnum(r[1])
            o.append(f'| {r[0]} | {d5} | {fnum(r[2])} | {fnum(r[3])} |')
    o += ["", f'> {d["table_note"]}', "", "**② 원인 사슬 (시간순)**", "", "| 시점 | 사건·수치 | 확신·출처 |", "|---|---|---|"]
    o += [f'| {c["when"]} | {c["fact"]} | {c["conf"]} |' for c in d["chain"]]
    o += ["", "**③ 원인 순위**", "", "| 순위 | 원인 | 근거 | 확신 |", "|---|---|---|---|"]
    o += [f'| {i} | {c["title"]} | {c["evidence"]} | {c["conf"]} |' for i, c in enumerate(d["causes"], 1)]
    o += ["", "**④ 분석 판단 (추정 포함)**", ""] + [f'- {x}' for x in d["judgement"]]
    o += ["", "**⑤ 아직 모르는 것과 반증 조건**", ""] + [f'- {x}' for x in d["unknown"]]
    o += ["", f'**⑥ 다음 거래일 시사점** — {d["outlook"]}', "",
          "출처: " + " · ".join(f'[{s["title"]}]({s["url"]})' for s in d["sources"]), "", E]
    return "\n".join(o)


def inject(text, block, anchor_re):
    if S in text and E in text:
        return re.sub(re.escape(S) + r".*?" + re.escape(E), lambda m: block, text, count=1, flags=re.S)
    m = re.search(anchor_re, text, flags=re.M)
    assert m, anchor_re
    return text[:m.start()] + block + "\n\n" + text[m.start():]


def main():
    date = sys.argv[1]
    d = json.load(open("docs/cause_analysis.json", encoding="utf-8"))
    T = "scripts/report_template.html"; M = f"reports/sk-hynix/{date}.md"
    t = open(T, encoding="utf-8").read()
    t = inject(t, render_html(d), r'^<section>\n<h2><span class="no">02</span>')
    open(T, "w", encoding="utf-8").write(t)
    m = open(M, encoding="utf-8").read()
    m = inject(m, render_md(d), r'^## 시세')
    open(M, "w", encoding="utf-8").write(m)
    print("cause block ok", d["asof"])


if __name__ == "__main__":
    main()
