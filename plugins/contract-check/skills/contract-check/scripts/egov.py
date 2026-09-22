#!/usr/bin/env python3
"""e-Gov 法令API (Version 2) の薄いCLIラッパー。

契約書チェック中に「この条項は法令に抵触しないか」を確認するとき、
記憶に頼らず現行条文を取りに行くために使う。

使い方:
    python3 egov.py laws                      # 契約チェックで頻出する法令のID一覧
    python3 egov.py search 下請                # 法令名の部分一致で法令IDを探す
    python3 egov.py article 民法 415           # 第415条を取得（略称 or law_id）
    python3 egov.py article 民法 398-2         # 第398条の2（枝番はハイフン）
    python3 egov.py article 労基法 15 --json   # 生のJSONが欲しいとき
    python3 egov.py keyword 秘密保持 --limit 5 # 条文本文の全文検索

APIキー不要。ネットワークが使えない環境ではエラーを返すので、
その場合はレポートに「条文未確認」と明示すること（うろ覚えで断定しない）。
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://laws.e-gov.go.jp/api/2"
PAGE = "https://laws.e-gov.go.jp/law/"

# 契約書チェックで参照頻度が高い法令。law_id は API で実在確認済み（2026-09時点）。
KNOWN = {
    "民法": "129AC0000000089",
    "商法": "132AC0000000048",
    "労働基準法": "322AC0000000049",
    "労基法": "322AC0000000049",
    "労働基準法施行規則": "322M40000100023",
    "労働契約法": "419AC0000000128",
    "労契法": "419AC0000000128",
    "労働者派遣法": "360AC0000000088",
    "独占禁止法": "322AC0000000054",
    "独禁法": "322AC0000000054",
    # 旧・下請代金支払遅延等防止法。2025年改正で改称、2026-01-01施行。
    "取適法": "331AC0000000120",
    "中小受託取引適正化法": "331AC0000000120",
    "下請法": "331AC0000000120",
    "下請振興法": "345AC0000000145",
    "フリーランス法": "505AC0000000025",
    "特定受託事業者法": "505AC0000000025",
    "個人情報保護法": "415AC0000000057",
    "著作権法": "345AC0000000048",
    "特許法": "334AC0000000121",
    "不正競争防止法": "405AC0000000047",
    "不競法": "405AC0000000047",
    "消費者契約法": "412AC0000000061",
    "建設業法": "324AC0000000100",
    "借地借家法": "403AC0000000090",
    "印紙税法": "342AC0000000023",
    "電子帳簿保存法": "410AC0000000025",
}


def _get(path, params):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "contract-check-skill"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"[egov] HTTP {e.code}: {body}")
    except Exception as e:  # ネットワーク不通など
        sys.exit(f"[egov] 取得失敗: {e}")


def resolve(name):
    """略称・法令名・law_id のいずれからも law_id を返す。"""
    if name in KNOWN:
        return KNOWN[name]
    if len(name) >= 15 and name[:3].isdigit():  # 既に law_id 形式
        return name
    d = _get("laws", {"law_title": name, "limit": 5})
    laws = d.get("laws") or []
    if not laws:
        sys.exit(f"[egov] 法令が見つかりません: {name}")
    return laws[0]["law_info"]["law_id"]


def flatten(node, out, depth=0):
    """light JSON の条文ツリーを読める行に落とす。"""
    if isinstance(node, dict):
        for key in ("ArticleCaption", "ArticleTitle", "ParagraphNum",
                    "ItemTitle", "Subitem1Title", "Subitem2Title"):
            if node.get(key):
                out.append(("title", key, str(node[key])))
        if "Sentence" in node:
            s = node["Sentence"]
            out.append(("text", "", "".join(s) if isinstance(s, list) else str(s)))
        for k, v in node.items():
            if k in ("Sentence",):
                continue
            if isinstance(v, (dict, list)):
                flatten(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            flatten(v, out, depth)


def render(full_text):
    out = []
    flatten(full_text, out)
    lines, buf = [], ""
    for kind, key, val in out:
        if kind == "title":
            if buf:
                lines.append(buf)
                buf = ""
            lines.append(val if key != "ParagraphNum" else f"\n{val}")
        else:
            buf += val
    if buf:
        lines.append(buf)
    return "\n".join(l for l in lines if l.strip())


def cmd_search(a):
    d = _get("laws", {"law_title": a.title, "limit": a.limit})
    for law in d.get("laws", []):
        li, ri = law["law_info"], law["revision_info"]
        print(f'{li["law_id"]}  {ri["law_title"]}')
        print(f'    法令番号: {li["law_num"]}  略称: {ri.get("abbrev") or "-"}')
        print(f'    最終改正施行: {ri.get("amendment_enforcement_date") or "-"}  {PAGE}{li["law_id"]}')


def cmd_article(a):
    law_id = resolve(a.law)
    elm = "MainProvision-Article_" + a.article.replace("-", "_").replace("の", "_")
    d = _get(f"law_data/{urllib.parse.quote(law_id)}", {"elm": elm, "json_format": "light"})
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return
    ri = d.get("revision_info", {})
    print(f'【{ri.get("law_title")}】{d.get("law_info", {}).get("law_num")}')
    print(f'最終改正施行日: {ri.get("amendment_enforcement_date") or "-"} / 出典: {PAGE}{law_id}')
    print("-" * 60)
    print(render(d.get("law_full_text")))


def cmd_keyword(a):
    d = _get("keyword", {"keyword": a.word, "limit": a.limit})
    if d.get("code"):
        print(f'ヒットなし: {d.get("message")}')
        return
    print(f'総ヒット数: {d.get("total_count")}')
    for it in d.get("items", []):
        ri, li = it["revision_info"], it["law_info"]
        print(f'\n■ {ri["law_title"]} ({li["law_id"]})  {PAGE}{li["law_id"]}')
        txt = json.dumps(it.get("sentence") or it.get("sentences") or "", ensure_ascii=False)
        print("  " + txt[:300])


def cmd_laws(a):
    seen = {}
    for k, v in KNOWN.items():
        seen.setdefault(v, []).append(k)
    for law_id, names in seen.items():
        print(f'{law_id}  {" / ".join(names)}  {PAGE}{law_id}')


def main():
    p = argparse.ArgumentParser(description="e-Gov 法令API v2 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="法令名で検索し law_id を得る")
    s.add_argument("title")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("article", help="条文を取得する")
    s.add_argument("law", help="略称・法令名・law_id")
    s.add_argument("article", help="条番号。枝番は 398-2 のように指定")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_article)

    s = sub.add_parser("keyword", help="条文本文の全文検索")
    s.add_argument("word")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(func=cmd_keyword)

    s = sub.add_parser("laws", help="内蔵の主要法令ID一覧")
    s.set_defaults(func=cmd_laws)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
