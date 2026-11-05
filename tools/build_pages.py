#!/usr/bin/env python3
"""index.html の辞書（DEPTS・DATA）から、商品ごとのページ・商品一覧・sitemap.xml を作る。

使い方: python3 tools/build_pages.py   （index.html を直したら毎回実行する）
出力:   item/<商品名>/index.html, item/index.html, sitemap.xml
見た目・表示切替・アクセス解析は index.html の目印（shared-head / gc / prefs / prefs-js）の間をそのまま使う。
"""
import datetime
import html
import re
import shutil
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://kt004.github.io/category-finder/"
SITE = "Amazonカテゴリ逆引き"
CAVEAT = "※ 表示する売り場や分類は Amazon の画面で一つずつ確かめたものではありません。参考程度にご覧ください。"

src = (ROOT / "index.html").read_text(encoding="utf-8")


def between(start, end):
    m = re.search(re.escape(start) + r".*?\n(.*?)" + re.escape(end), src, re.S)
    if not m:
        raise SystemExit(f"目印が見つかりません: {start}")
    return m.group(1)


SHARED_HEAD = between("<!-- shared-head:start", "<!-- shared-head:end -->")
GC = between("<!-- gc:start -->", "<!-- gc:end -->")
PREFS = between("<!-- prefs:start -->", "<!-- prefs:end -->")
PREFS_JS = between("// prefs-js:start", "// prefs-js:end")

DEPTS = {k: (name, alias) for k, name, alias in
         re.findall(r'^\s+(\w+):\s+\["([^"]+)", "([^"]+)"\]', src.split("const DEPTS = {")[1].split("};")[0], re.M)}

ITEMS = []
for line in src.split("const DATA = `")[1].split("`")[0].strip().splitlines():
    name, aliases, paths = line.split("|")
    places = []
    for p in paths.split(";"):
        d, _, rest = p.partition(":")
        places.append((d, rest.split(">") if rest else []))
    ITEMS.append({"name": name, "aliases": [a for a in aliases.split(",") if a], "places": places})


def slug(name):  # index.html の slug() と同じ規則
    return name.replace("（", "-").replace("）", "")


def plain(name):  # 検索に使う名前（「ドライバー（工具）」→「ドライバー」）
    return re.sub(r"（.*?）", "", name)


def item_href(name, prefix):
    return prefix + urllib.parse.quote(slug(name)) + "/"


def amazon(k, alias=None):
    return "https://www.amazon.co.jp/s?k=" + urllib.parse.quote(k) + (f"&i={alias}" if alias else "")


e = html.escape


def place_text(d, sub):
    return "「" + " › ".join([DEPTS[d][0]] + sub) + "」"


def page(title, desc, url, body, og_type="article", extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}og.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
{extra_head}{SHARED_HEAD}{GC}</head>
<body>
<div class="wrap">
{PREFS}{body}
  <footer>
    <p>このページは Amazon とは関係のない個人の非公式ツールです。カテゴリ名と階層は 2026年11月時点の Amazon.co.jp の売り場構成をもとにした目安で、Amazon 側の変更により名前や位置が変わることがあります。正確な位置は「Amazon全体で検索」から確かめてください。</p>
    <p>閲覧数を数えるために、Cookie を使わないアクセス解析（GoatCounter）を使っています。</p>
  </footer>
</div>
<script>
{PREFS_JS}</script>
</body>
</html>
"""


def item_page(it):
    name, kw = it["name"], plain(it["name"])
    url = BASE + "item/" + urllib.parse.quote(slug(name)) + "/"
    (d0, sub0), others = it["places"][0], it["places"][1:]
    answer = f"{e(kw)}は Amazon.co.jp では主に<strong>{e(place_text(d0, sub0))}</strong>に並んでいます。"
    if others:
        answer += "ほかに" + "、".join(e(place_text(d, s)) for d, s in others) + "にもあります。"
    desc = re.sub(r"<.*?>", "", answer) + "売り場を絞った Amazon 検索へのリンク付き（非公式・参考情報）。"

    rows = []
    for i, (d, sub) in enumerate(it["places"]):
        dname, alias = DEPTS[d]
        crumbs = "".join(('<span class="sep" aria-hidden="true">›</span>' if j else "") + f"<span>{e(s)}</span>" for j, s in enumerate(sub))
        rows.append(f"""      <div class="place{' first' if i == 0 else ''}">
        <span class="rank">{'主な売り場' if i == 0 else 'ここにもある'}</span>
        <div class="path">
          <span class="dept">{e(dname)}</span>
          {f'<div class="crumbs" aria-label="階層">{crumbs}</div>' if crumbs else ''}
          <div class="actions"><a class="btn" href="{e(amazon(kw, alias))}" target="_blank" rel="noopener">「{e(dname)}」で「{e(kw)}」を検索</a></div>
        </div>
      </div>""")

    related = [x for x in ITEMS if x["places"][0][0] == d0 and x is not it]
    chips = "".join(f'<a class="chip" href="{item_href(x["name"], "../")}">{e(x["name"])}</a>' for x in related)
    aliases = f'<p class="aliases">別の呼び方: {e("、".join(it["aliases"]))}</p>' if it["aliases"] else ""
    crumb_ld = (
        '<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":['
        f'{{"@type":"ListItem","position":1,"name":"{SITE}","item":"{BASE}"}},'
        f'{{"@type":"ListItem","position":2,"name":"商品一覧","item":"{BASE}item/"}},'
        f'{{"@type":"ListItem","position":3,"name":"{e(name)}","item":"{url}"}}]}}</script>\n'
    )
    body = f"""  <nav class="bc" aria-label="現在の場所"><a href="../../">{SITE}</a><span aria-hidden="true">›</span><a href="../">商品一覧</a><span aria-hidden="true">›</span><span>{e(name)}</span></nav>
  <header>
    <h1 class="page-h1">「{e(kw)}」は Amazon のどのカテゴリ？</h1>
    <p class="answer">{answer}</p>
    {aliases}
    <p class="caveat">{CAVEAT}</p>
  </header>
  <div class="item-body">
    <article class="sign-card main">
      <div class="sign-head"><h2 class="item-name">{e(name)}</h2></div>
      <div class="places">
{chr(10).join(rows)}
      </div>
    </article>
    <div><a class="btn" href="{e(amazon(kw))}" target="_blank" rel="noopener">Amazon全体で「{e(kw)}」を検索</a></div>
    <aside class="howto">
      <h2>Amazon の画面で確かめる方法</h2>
      <ol>
        <li>上の「Amazon全体で検索」を押し、検索結果を開きます。</li>
        <li>検索結果から商品を選んで商品ページを開くと、ページ上部に「家電&amp;カメラ › アクセサリ・サプライ › …」のような売り場の階層が表示されます。</li>
      </ol>
    </aside>
    {f'<section class="related"><h2>「{e(DEPTS[d0][0])}」のほかの商品</h2><div class="chips">{chips}</div></section>' if chips else ''}
    <section>
      <h2>ほかの商品を調べる</h2>
      <form class="goto" action="../../" method="get" role="search">
        <input name="q" type="search" aria-label="商品の名前" enterkeyhint="search">
        <button type="submit">調べる</button>
      </form>
    </section>
  </div>
"""
    title = f"{kw}はAmazonのどのカテゴリ？売り場と検索リンク｜{SITE}"
    return url, page(title, desc, url, body, extra_head=crumb_ld)


def index_page():
    url = BASE + "item/"
    boxes = []
    for k, (dname, alias) in DEPTS.items():
        items = [x for x in ITEMS if x["places"][0][0] == k]
        if not items:
            continue
        chips = "".join(f'<a class="chip" href="{item_href(x["name"], "")}">{e(x["name"])}</a>' for x in items)
        boxes.append(f'      <div class="dept-box"><h3><span>{e(dname)}</span><a href="https://www.amazon.co.jp/s?i={alias}&amp;k=" target="_blank" rel="noopener">Amazonで開く</a></h3><div class="chips">{chips}</div></div>')
    body = f"""  <nav class="bc" aria-label="現在の場所"><a href="../">{SITE}</a><span aria-hidden="true">›</span><span>商品一覧</span></nav>
  <header>
    <h1 class="page-h1">商品一覧（{len(ITEMS)}商品）</h1>
    <p class="lead">商品名を押すと、その商品が Amazon.co.jp のどの売り場（カテゴリ）に並んでいるかを表示します。商品は、いちばん多く並ぶ売り場ごとに分けています。</p>
    <p class="caveat">{CAVEAT}</p>
  </header>
  <section>
    <div class="dept-list">
{chr(10).join(boxes)}
    </div>
  </section>
"""
    title = f"商品一覧（{len(ITEMS)}商品）｜{SITE}"
    desc = f"{SITE}で調べられる{len(ITEMS)}商品の一覧。家電・パソコン・日用品・食品・ファッション・ペット用品などを、Amazon.co.jp の売り場ごとに並べています。"
    return url, page(title, desc, url, body, og_type="website")


def main():
    out = ROOT / "item"
    if out.exists():
        shutil.rmtree(out)  # 辞書から消えた商品のページを残さない
    urls = [BASE]
    url, doc = index_page()
    out.mkdir()
    (out / "index.html").write_text(doc, encoding="utf-8")
    urls.append(url)
    seen = set()
    for it in ITEMS:
        s = slug(it["name"])
        if s in seen:
            raise SystemExit(f"同じ場所になる商品名があります: {s}")
        seen.add(s)
        url, doc = item_page(it)
        (out / s).mkdir()
        (out / s / "index.html").write_text(doc, encoding="utf-8")
        urls.append(url)
    today = datetime.date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls]
    sm.append("</urlset>\n")
    (ROOT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    print(f"商品ページ {len(ITEMS)} 件・商品一覧・sitemap.xml（{len(urls)} URL）を作りました")


main()
