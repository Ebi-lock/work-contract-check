#!/usr/bin/env python3
"""契約書チェック結果のMarkdownレポートを、単体で開けるHTMLに変換する。

外部依存なし・単一ファイル出力なので、そのままメール添付や社内共有ができる。
リスク階級（🔴🟡🔵）で色分けし、絞り込みボタン・目次・修正案のコピーボタン・
印刷用スタイルを付ける。

使い方:
    python3 render_report.py 契約書チェック結果_業務委託契約書_20260921.md
    python3 render_report.py report.md -o /path/to/out.html
    python3 render_report.py report.md --title "業務委託契約書レビュー"

対応するMarkdown記法は report-format.md のテンプレートが使う範囲
（見出し・表・引用・箇条書き・コードブロック・強調・リンク・水平線）。
"""

import argparse
import html
import os
import re
import sys

RISK = {"🔴": "high", "🟡": "mid", "🔵": "low", "⬜": "missing", "❌": "high", "⚠️": "mid", "✅": "ok"}

CSS = """
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#1a1d21; --muted:#5b6672; --line:#dfe3e8;
  --high:#c62828; --high-bg:#fdecea; --mid:#b26a00; --mid-bg:#fff6e5;
  --low:#1565c0; --low-bg:#e9f2fc; --missing:#546e7a; --missing-bg:#eceff1;
  --ok:#2e7d32; --quote-bg:#f0f2f5; --fix-bg:#f1f8f2; --fix-line:#82b88a;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#15181c; --panel:#1d2126; --ink:#e6e9ed; --muted:#9aa5b1; --line:#2f353c;
    --high:#ff8a80; --high-bg:#3a2320; --mid:#ffcc80; --mid-bg:#3a3020;
    --low:#90caf9; --low-bg:#1e2b3a; --missing:#b0bec5; --missing-bg:#262c31;
    --ok:#a5d6a7; --quote-bg:#23282e; --fix-bg:#1f2a21; --fix-line:#4c7a55;
  }
}
:root[data-theme="dark"]{
  --bg:#15181c; --panel:#1d2126; --ink:#e6e9ed; --muted:#9aa5b1; --line:#2f353c;
  --high:#ff8a80; --high-bg:#3a2320; --mid:#ffcc80; --mid-bg:#3a3020;
  --low:#90caf9; --low-bg:#1e2b3a; --missing:#b0bec5; --missing-bg:#262c31;
  --ok:#a5d6a7; --quote-bg:#23282e; --fix-bg:#1f2a21; --fix-line:#4c7a55;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Hiragino Kaku Gothic ProN","Hiragino Sans","Yu Gothic",Meiryo,
    -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.85; font-feature-settings:"palt";
}
.wrap{display:grid; grid-template-columns:260px minmax(0,1fr); gap:28px;
  max-width:1220px; margin:0 auto; padding:28px 16px 80px}
nav{position:sticky; top:24px; align-self:start; max-height:calc(100vh - 48px);
  overflow-y:auto; font-size:13px; line-height:1.6}
nav .navhead{font-weight:700; letter-spacing:.04em; color:var(--muted);
  text-transform:uppercase; font-size:11px; margin:0 0 10px}
nav a{display:block; padding:5px 10px; color:var(--muted); text-decoration:none;
  border-left:2px solid transparent; border-radius:0 4px 4px 0}
nav a:hover{color:var(--ink); background:var(--panel)}
nav a.lv3{padding-left:22px; font-size:12px}
nav a.on{color:var(--ink); border-left-color:var(--high); background:var(--panel)}
main{min-width:0; background:var(--panel); border:1px solid var(--line);
  border-radius:10px; padding:36px 40px}
h1{font-size:25px; line-height:1.45; margin:0 0 6px; letter-spacing:.01em}
h2{font-size:19px; margin:44px 0 14px; padding-bottom:8px; border-bottom:2px solid var(--line)}
h3{font-size:16px; margin:26px 0 10px}
h4{font-size:14px; margin:18px 0 8px; color:var(--muted)}
p{margin:10px 0}
a{color:var(--low)}
hr{border:0; border-top:1px solid var(--line); margin:32px 0}
ul,ol{margin:10px 0; padding-left:1.5em}
li{margin:5px 0}
code{background:var(--quote-bg); padding:1px 5px; border-radius:4px;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.88em}
pre{background:var(--quote-bg); border:1px solid var(--line); border-radius:8px;
  padding:14px 16px; overflow-x:auto; font-size:13px; line-height:1.6}
pre code{background:none; padding:0}
blockquote{margin:12px 0; padding:12px 16px; background:var(--quote-bg);
  border-left:3px solid var(--muted); border-radius:0 6px 6px 0;
  color:var(--ink); font-size:14px}
blockquote p{margin:4px 0}
table{border-collapse:collapse; width:100%; margin:14px 0; font-size:13.5px}
th,td{border:1px solid var(--line); padding:8px 11px; text-align:left;
  vertical-align:top; word-break:break-word}
th{background:var(--quote-bg); font-weight:700; white-space:nowrap}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--quote-bg) 45%,transparent)}
.meta{color:var(--muted); font-size:12.5px; margin:0 0 22px}
.pill{display:inline-block; padding:1px 9px; border-radius:999px;
  font-size:12px; font-weight:700; white-space:nowrap; border:1px solid transparent}
.pill.high{color:var(--high); background:var(--high-bg); border-color:var(--high)}
.pill.mid{color:var(--mid); background:var(--mid-bg); border-color:var(--mid)}
.pill.low{color:var(--low); background:var(--low-bg); border-color:var(--low)}
.pill.missing{color:var(--missing); background:var(--missing-bg); border-color:var(--missing)}
.filters{display:flex; gap:8px; flex-wrap:wrap; margin:18px 0 6px;
  padding:12px; background:var(--quote-bg); border-radius:8px; align-items:center}
.filters .lbl{font-size:12px; color:var(--muted); margin-right:2px}
.filters button{font:inherit; font-size:13px; cursor:pointer; padding:4px 14px;
  border-radius:999px; border:1px solid var(--line); background:var(--panel);
  color:var(--ink)}
.filters button[aria-pressed="true"]{border-color:var(--ink); font-weight:700}
.finding{border:1px solid var(--line); border-left-width:4px; border-radius:8px;
  padding:4px 20px 16px; margin:18px 0; background:var(--panel)}
.finding[data-risk="high"]{border-left-color:var(--high); background:color-mix(in srgb,var(--high-bg) 32%,var(--panel))}
.finding[data-risk="mid"]{border-left-color:var(--mid); background:color-mix(in srgb,var(--mid-bg) 32%,var(--panel))}
.finding[data-risk="low"]{border-left-color:var(--low)}
.finding[data-risk="missing"]{border-left-color:var(--missing)}
.finding h3{margin-top:14px}
.fix{background:var(--fix-bg); border:1px solid var(--fix-line); border-radius:8px;
  padding:12px 14px; margin:12px 0; position:relative}
.fix .tag{font-size:11px; font-weight:700; letter-spacing:.06em; color:var(--ok);
  display:block; margin-bottom:4px}
.fix .copy{position:absolute; top:9px; right:10px; font:inherit; font-size:11.5px;
  cursor:pointer; padding:2px 10px; border-radius:6px; border:1px solid var(--fix-line);
  background:var(--panel); color:var(--ink)}
.disclaimer{margin-top:34px; padding:14px 18px; border:1px dashed var(--line);
  border-radius:8px; color:var(--muted); font-size:13px; background:var(--quote-bg)}
.toggle{position:fixed; right:18px; bottom:18px; z-index:9; font:inherit; font-size:12px;
  cursor:pointer; padding:7px 13px; border-radius:999px; border:1px solid var(--line);
  background:var(--panel); color:var(--ink); box-shadow:0 2px 10px rgba(0,0,0,.14)}
@media (max-width:900px){
  .wrap{grid-template-columns:1fr; padding:16px 16px 64px; gap:16px}
  nav{position:static; max-height:none; border-bottom:1px solid var(--line); padding-bottom:12px}
  nav a.lv3{display:none}
  main{padding:22px 18px; border-radius:8px}
  h1{font-size:21px}
  table{font-size:12.5px}
  th{white-space:normal}
}
@media print{
  :root{--bg:#fff; --panel:#fff}
  body{font-size:10.5pt; line-height:1.6}
  .wrap{display:block; max-width:none; padding:0}
  nav,.filters,.toggle,.fix .copy{display:none}
  main{border:0; padding:0}
  .finding{break-inside:avoid; page-break-inside:avoid}
  h2{break-after:avoid}
  a{color:inherit; text-decoration:none}
}
"""

JS = """
(function(){
  var btns=document.querySelectorAll('.filters button');
  btns.forEach(function(b){
    b.addEventListener('click',function(){
      var f=b.dataset.filter;
      btns.forEach(function(x){x.setAttribute('aria-pressed', x===b?'true':'false')});
      document.querySelectorAll('.finding').forEach(function(el){
        el.style.display=(f==='all'||el.dataset.risk===f)?'':'none';
      });
    });
  });
  document.querySelectorAll('.fix .copy').forEach(function(b){
    b.addEventListener('click',function(){
      var t=b.parentNode.querySelector('.fixbody');
      navigator.clipboard.writeText(t?t.innerText.trim():'').then(function(){
        var o=b.textContent; b.textContent='コピーしました';
        setTimeout(function(){b.textContent=o},1400);
      });
    });
  });
  var tgl=document.querySelector('.toggle');
  if(tgl){tgl.addEventListener('click',function(){
    var cur=document.documentElement.getAttribute('data-theme');
    var dark=window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next=(cur? cur==='dark' : dark) ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme',next);
  })}
  var links=[].slice.call(document.querySelectorAll('nav a'));
  var heads=links.map(function(a){return document.getElementById(a.hash.slice(1))}).filter(Boolean);
  function onScroll(){
    var y=window.scrollY+120, cur=null;
    heads.forEach(function(h){ if(h.offsetTop<=y) cur=h; });
    links.forEach(function(a){ a.classList.toggle('on', !!cur && a.hash==='#'+cur.id); });
  }
  window.addEventListener('scroll',onScroll,{passive:true}); onScroll();
})();
"""


def esc(t):
    return html.escape(t, quote=False).replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")


def inline(t):
    t = esc(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    t = re.sub(r"(?<!\()(?<!\")(https?://[^\s<>\)｜|、。]+)",
               r'<a href="\1" target="_blank" rel="noopener">\1</a>', t)
    return t


def risk_of(text):
    for mark, cls in RISK.items():
        if mark in text:
            return cls if cls != "ok" else None
    return None


def slug(text, used):
    m = re.search(r"\[([A-Z]+-\d+)\]", text)
    base = m.group(1) if m else re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff]+", "-", text).strip("-")[:40]
    base = base or "sec"
    n, s = 1, base
    while s in used:
        n += 1
        s = f"{base}-{n}"
    used.add(s)
    return s


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def badge(cell):
    c = risk_of(cell)
    if c and len(cell.strip()) <= 4:
        label = {"high": "高", "mid": "中", "low": "低", "missing": "欠落"}.get(c, "")
        return f'<span class="pill {c}">{esc(cell.strip())} {label}</span>'
    return inline(cell)


def convert(md):
    """Markdown を本文HTML・目次項目・H1タイトルに変換する。"""
    lines = md.split("\n")
    out, toc, used = [], [], set()
    title = None
    i, n = 0, len(lines)
    section_risk = None
    open_finding = False

    def close_finding():
        nonlocal open_finding
        if open_finding:
            out.append("</section>")
            open_finding = False

    while i < n:
        ln = lines[i]

        # コードブロック
        if ln.startswith("```"):
            lang = ln[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>" + esc("\n".join(buf)) + "</code></pre>")
            continue

        # 見出し
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl, txt = len(m.group(1)), m.group(2).strip()
            if lvl == 1 and title is None:
                title = re.sub(r"<[^>]+>", "", txt)
                i += 1
                continue
            close_finding()
            sid = slug(txt, used)
            if lvl == 2:
                section_risk = risk_of(txt)
                toc.append((2, sid, txt))
                out.append(f'<h2 id="{sid}">{inline(txt)}</h2>')
            elif lvl == 3:
                r = risk_of(txt) or section_risk
                toc.append((3, sid, txt))
                if r:
                    out.append(f'<section class="finding" data-risk="{r}">')
                    open_finding = True
                out.append(f'<h3 id="{sid}">{inline(txt)}</h3>')
            else:
                out.append(f'<h{lvl} id="{sid}">{inline(txt)}</h{lvl}>')
            i += 1
            continue

        # 水平線
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", ln):
            close_finding()
            out.append("<hr>")
            i += 1
            continue

        # 表
        if ln.strip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[i + 1]):
            head = cells(ln)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            tb = ""
            for r in rows:
                tb += "<tr>" + "".join(f"<td>{badge(c)}</td>" for c in r) + "</tr>"
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>")
            continue

        # 引用
        if ln.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").lstrip())
                i += 1
            body = "".join(f"<p>{inline(b)}</p>" for b in buf if b.strip())
            out.append(f"<blockquote>{body}</blockquote>")
            continue

        # 箇条書き
        if re.match(r"^\s*([-*+]|\d+\.)\s+", ln):
            ordered = bool(re.match(r"^\s*\d+\.\s+", ln))
            items, base_indent = [], len(ln) - len(ln.lstrip())
            while i < n and (re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i])
                             or (lines[i].strip() and lines[i].startswith(" " * (base_indent + 2)))):
                mm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
                if mm:
                    items.append((len(mm.group(1)), mm.group(3)))
                elif items:
                    # 継続行。修正案を引用記法で書いているケースがあるので > を落とす
                    cont = re.sub(r"^>\s?", "", lines[i].strip())
                    if cont:
                        items[-1] = (items[-1][0], items[-1][1] + "<br>" + cont)
                i += 1
            html_items, depth = [], base_indent
            for ind, txt in items:
                if ind > depth:
                    html_items.append("<ul>")
                    depth = ind
                elif ind < depth:
                    html_items.append("</ul>")
                    depth = ind
                # 修正案はコピーできるブロックにする（そのまま相手に送れる形で渡すため）
                fm = re.match(r"^\*\*(修正案|推奨する条文案|推奨条文案|代替案)\*\*[:：]\s*(.+)$", txt, re.S)
                if fm:
                    body_txt = re.sub(r"(^|<br>)>\s?", r"\1", fm.group(2)).strip()
                    body_txt = re.sub(r"^(<br>)+|(<br>)+$", "", body_txt)
                    html_items.append(
                        f'<li><div class="fix"><span class="tag">{esc(fm.group(1))}</span>'
                        f'<button class="copy" type="button">コピー</button>'
                        f'<div class="fixbody">{inline(body_txt)}</div></div></li>')
                else:
                    html_items.append(f"<li>{inline(txt)}</li>")
            while depth > base_indent:
                html_items.append("</ul>")
                depth -= 2
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(html_items) + f"</{tag}>")
            continue

        # 空行
        if not ln.strip():
            i += 1
            continue

        # 段落
        buf = []
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|>|\s*([-*+]|\d+\.)\s|\||```|\s*(-{3,}|\*{3,}|_{3,})\s*$)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")

    close_finding()
    return "\n".join(out), toc, title


def build(md, title_override=None, source=""):
    body, toc, h1 = convert(md)
    title = title_override or h1 or "契約書チェック結果"
    nav = "".join(
        f'<a class="lv{lvl}" href="#{sid}">{esc(re.sub(r"[*`]", "", txt))}</a>'
        for lvl, sid, txt in toc)
    has_findings = 'class="finding"' in body
    filters = ""
    if has_findings:
        filters = (
            '<div class="filters"><span class="lbl">絞り込み</span>'
            '<button type="button" data-filter="all" aria-pressed="true">すべて</button>'
            '<button type="button" data-filter="high">🔴 高</button>'
            '<button type="button" data-filter="mid">🟡 中</button>'
            '<button type="button" data-filter="low">🔵 低</button>'
            '<button type="button" data-filter="missing">⬜ 欠落</button></div>')
    src = f"出力元: {esc(os.path.basename(source))}" if source else ""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23c62828'/%3E%3Cpath d='M20 16h18l8 8v24H20z' fill='%23fff'/%3E%3Cpath d='M26 32h16M26 39h12' stroke='%23c62828' stroke-width='3'/%3E%3C/svg%3E">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<nav><p class="navhead">目次</p>{nav}</nav>
<main>
<h1>{esc(title)}</h1>
<p class="meta">{src}</p>
{filters}
{body}
<p class="disclaimer">本レポートは契約書の記載内容に基づく一般的な指摘であり、法的助言ではありません。事実関係や取引の経緯によって結論は変わり得ます。最終的な判断は弁護士にご確認ください。</p>
</main>
</div>
<button class="toggle" type="button">表示切替</button>
<script>{JS}</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="契約書チェック結果のMarkdownをHTMLに変換")
    ap.add_argument("markdown", help="入力のMarkdownレポート")
    ap.add_argument("-o", "--output", help="出力先HTML（既定: 入力と同じ場所・同じ名前の .html）")
    ap.add_argument("--title", help="ページタイトル（既定: Markdownのh1）")
    a = ap.parse_args()

    if not os.path.exists(a.markdown):
        sys.exit(f"[render] 入力が見つかりません: {a.markdown}")
    md = open(a.markdown, encoding="utf-8").read()
    out = a.output or os.path.splitext(a.markdown)[0] + ".html"
    open(out, "w", encoding="utf-8").write(build(md, a.title, a.markdown))
    print(f"[render] HTMLを出力しました: {out}")
    print(f"[render] サイズ: {os.path.getsize(out):,} bytes")


if __name__ == "__main__":
    main()
