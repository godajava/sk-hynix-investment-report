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


CHAIN_N = 5          # 압축 표에 보이는 최근 사슬 항목 수
DAILY_N = 2          # 압축 표에 보이는 최근 일별 원인 수
JUDGE_N = 3          # ④ 분석 판단에 보이는 최근 항목 수(나머지는 펼치기)
_LBL = re.compile(r"(높음~중간|중간~높음|중간~낮음|낮음~중간|높음|중간|낮음)")


def short_text(c, key, n=110):
    if c.get("short"):
        return c["short"]
    t = c[key]
    if len(t) <= n:
        return t
    cut = max(t.rfind(sep, 0, n) for sep in ("·", ",", " "))
    return t[:cut if cut > 40 else n].rstrip(" ·,") + "…"


def conf_label(c):
    if c.get("conf_short"):
        return c["conf_short"]
    m = _LBL.search(c["conf"])
    return m.group(1) if m else c["conf"][:20]


def split_causes(causes):
    daily = [c for c in causes if re.match(r"\(\d+/\d+ (결과|장중)\)|\(오늘", c["title"])]
    struct = [c for c in causes if c not in daily]
    return daily, struct


def daily_tag(c):
    m = re.match(r"\((\d+/\d+) 결과\)", c["title"])
    return m.group(1) if m else "오늘"


def render_html(d):
    o = [S, "<section>",
         f'<h2><span class="no">WHY</span>주간 변동 원인 분석 — 국내·해외·미국 빅테크 '
         f'<small style="font-size:12px;font-weight:500;color:var(--muted)">{e(d["week"])} · 기준 {e(d["asof"])}</small></h2>',
         f'<p><strong>한 줄 결론</strong> — {e(d["headline"])}</p>',
         f'<p style="color:var(--muted);font-size:12px">{e(d["method_note"])}</p>',
         '<p><strong>① 시장 현황 — 한국·미국 지수와 빅테크</strong></p>',
         f'<div class="tablewrap"><table class="kv why"><colgroup><col style="width:{30 if len(d.get("cols",[1,2,3]))>3 else 34}%">' + ''.join(f'<col style="width:{(70 if len(d.get("cols",[1,2,3]))>3 else 66)/len(d.get("cols",[1,2,3])):.1f}%">' for _ in d.get("cols",[1,2,3])) + '</colgroup>',
         '<tr><th>종목·지수</th>' + ''.join(f'<th>{e(c)}</th>' for c in d.get('cols',['11/5(목)','11/6(금)','주간'])) + '</tr>']
    ncol=len(d.get('cols',[1,2,3]))
    for g in d["table"]:
        o.append(f'<tr><th colspan="{ncol+1}" style="text-align:left">{e(g["group"])}</th></tr>')
        for r in g["rows"]:
            vals=list(r[1:])+[None]*(ncol-len(r[1:]))
            cells=''.join(('<td style="text-align:right;font-size:11px">'+e(v)+'</td>') if isinstance(v,str) else '<td class="num">'+cnum(v)+'</td>' for v in vals[:ncol])
            o.append(f'<tr><td>{e(r[0])}</td>{cells}</tr>')
    o += ['</table></div>', f'<p style="color:var(--muted);font-size:12px">{e(d["table_note"])}</p>',
          f'<p><strong>② 원인 사슬 — 최근 {min(CHAIN_N, len(d["chain"]))}건 요약</strong></p>',
          '<div class="tablewrap"><table class="kv why"><colgroup><col style="width:22%"><col style="width:58%"><col style="width:20%"></colgroup><tr><th>시점</th><th>핵심</th><th>확신</th></tr>']
    recent, older = d["chain"][-CHAIN_N:], d["chain"][:-CHAIN_N]
    for c in recent:
        o.append(f'<tr><td>{e(c["when"])}</td><td>{e(short_text(c, "fact"))}</td><td>{e(conf_label(c))}</td></tr>')
    o.append('</table></div>')
    def full_chain(rows):
        x = ['<div class="tablewrap"><table class="kv why"><colgroup><col style="width:21%"><col style="width:49%"><col style="width:30%"></colgroup><tr><th>시점</th><th>사건·수치</th><th>확신·출처</th></tr>']
        x += [f'<tr><td>{e(c["when"])}</td><td>{e(c["fact"])}</td><td>{e(c["conf"])}</td></tr>' for c in rows]
        return x + ['</table></div>']
    o.append(f'<details style="margin:4px 0 12px"><summary style="cursor:pointer;color:var(--muted);font-size:12.5px">원인 사슬 전체 보기 — 최근 {len(recent)}건 상세 + 이전 {len(older)}건</summary>')
    o += full_chain(older + recent)
    o.append('</details>')
    daily, struct = split_causes(d["causes"])
    o += ['<p><strong>③ 원인 순위 — 최근 일별 원인과 주간 구조 원인</strong></p>',
          '<div class="tablewrap"><table class="kv why"><colgroup><col style="width:12%"><col style="width:68%"><col style="width:20%"></colgroup><tr><th>구분</th><th>원인</th><th>확신</th></tr>']
    for c in daily[:DAILY_N]:
        o.append(f'<tr><td>{e(daily_tag(c))}</td><td>{e(short_text(c, "title", 120))}</td><td>{e(conf_label(c))}</td></tr>')
    for i, c in enumerate(struct, 1):
        o.append(f'<tr><td>구조 {i}</td><td>{e(c["title"])}</td><td>{e(conf_label(c))}</td></tr>')
    o.append('</table></div>')
    o.append(f'<details style="margin:4px 0 12px"><summary style="cursor:pointer;color:var(--muted);font-size:12.5px">원인 순위 근거 전체 보기 — 일별 {len(daily)}건 · 구조 {len(struct)}건</summary>')
    o.append('<div class="tablewrap"><table class="kv why"><colgroup><col style="width:8%"><col style="width:24%"><col style="width:46%"><col style="width:22%"></colgroup><tr><th>순위</th><th>원인</th><th>근거</th><th>확신</th></tr>')
    for i, c in enumerate(d["causes"], 1):
        o.append(f'<tr><td class="num">{i}</td><td>{e(c["title"])}</td><td>{e(c["evidence"])}</td><td>{e(c["conf"])}</td></tr>')
    o.append('</table></div></details>')
    jr, jo = d["judgement"][-JUDGE_N:], d["judgement"][:-JUDGE_N]
    o += [f'<p><strong>④ 분석 판단 (추정 포함) — 최근 {len(jr)}건</strong></p><ul>']
    o += [f'<li>{e(x)}</li>' for x in reversed(jr)]
    o += ['</ul>']
    if jo:
        o.append(f'<details style="margin:4px 0 12px"><summary style="cursor:pointer;color:var(--muted);font-size:12.5px">이전 분석 판단 {len(jo)}건 보기</summary><ul>')
        o += [f'<li>{e(x)}</li>' for x in reversed(jo)]
        o.append('</ul></details>')
    o += ['<p><strong>⑤ 아직 모르는 것과 반증 조건</strong></p><ul>']
    o += [f'<li>{e(x)}</li>' for x in d["unknown"]]
    o += ['</ul>', f'<p><strong>⑥ 다음 거래일 시사점</strong> — {e(d["outlook"])}</p>',
          '<p style="color:var(--muted);font-size:12px">출처(검색 요약 기준, 일부 원문 미열람): ' +
          ' · '.join(f'<a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["title"])}</a>' for s in d["sources"]) + '</p>',
          "</section>", E]
    return "\n".join(o)


def render_md(d):
    ncol=len(d.get('cols',[1,2,3]))
    o = [S, f'## 주간 변동 원인 분석 — 국내·해외·미국 빅테크 ({d["week"]}, 기준 {d["asof"]})', "",
         f'**한 줄 결론** — {d["headline"]}', "", f'> {d["method_note"]}', "",
         "**① 시장 현황**", "", "| 종목·지수 | " + " | ".join(d.get("cols",["11/5(목)","11/6(금)","주간"])) + " |", "|---|" + "---|" * len(d.get("cols",[1,2,3]))]
    for g in d["table"]:
        o.append(f'| **{g["group"]}** |' + ' |' * ncol)
        for r in g["rows"]:
            vals=list(r[1:])+[None]*(ncol-len(r[1:]))
            o.append(f'| {r[0]} | ' + ' | '.join(v if isinstance(v,str) else fnum(v) for v in vals[:ncol]) + ' |')
    o += ["", f'> {d["table_note"]}', "", f"**② 원인 사슬 — 최근 {min(CHAIN_N, len(d['chain']))}건 요약**", "", "| 시점 | 핵심 | 확신 |", "|---|---|---|"]
    o += [f'| {c["when"]} | {short_text(c, "fact")} | {conf_label(c)} |' for c in d["chain"][-CHAIN_N:]]
    daily, struct = split_causes(d["causes"])
    o += ["", f'_이전 사슬 {max(len(d["chain"]) - CHAIN_N, 0)}건과 항목별 상세 근거는 웹페이지의 펼치기 또는 docs/cause_analysis.json 참조._', "",
          "**③ 원인 순위 — 최근 일별 원인과 주간 구조 원인**", "", "| 구분 | 원인 | 확신 |", "|---|---|---|"]
    o += [f'| {daily_tag(c)} | {short_text(c, "title", 120)} | {conf_label(c)} |' for c in daily[:DAILY_N]]
    o += [f'| 구조 {i} | {c["title"]} | {conf_label(c)} |' for i, c in enumerate(struct, 1)]
    jr, jo = d["judgement"][-JUDGE_N:], d["judgement"][:-JUDGE_N]
    o += ["", f"**④ 분석 판단 (추정 포함) — 최근 {len(jr)}건**", ""] + [f'- {x}' for x in reversed(jr)]
    if jo:
        o += ["", f'_이전 분석 판단 {len(jo)}건은 웹페이지의 펼치기 또는 docs/cause_analysis.json 참조._']
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
