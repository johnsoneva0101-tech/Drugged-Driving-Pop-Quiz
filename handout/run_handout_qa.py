"""毒駕執法相關法規與實務彙編（線上講義，handout/index.html）自動化驗收。

用法（倉庫根目錄或 handout/ 內皆可）：
  python handout/run_handout_qa.py                 # 講義本身的全部檢查
  python handout/run_handout_qa.py --app <目錄>    # 另與 APP 原始檔比對（<目錄> 內放 APP 的 regulations.html、quick-card.html、assets/sop-*.png）
需求：Python 3、Playwright（Chromium）；--app 的並排截圖需 Pillow。輸出：handout/qa_output/（不納入版控）。
"""
import argparse, functools, json, re, socket, subprocess, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

HD = Path(__file__).resolve().parent
ROOT = HD.parent
OUT = HD / "qa_output"
SITE = "https://johnsoneva0101-tech.github.io/Drugged-Driving-Pop-Quiz/handout/"
TABS = ["sop", "cpc", "traf", "crim", "etc", "faq", "card", "about"]
TAB_NAMES = ["作業程序", "刑事訴訟法", "道交條例", "刑法", "其他法規", "常見問題", "速查卡", "關於"]
# 講稿關鍵字：講稿原表條數；APP（來源 427ae47）實際條數不同者以 APP 為準（不得為湊數修改內容），報告標出差異
SCRIPT_TABLE = {"均應填寫": 1, "始得": 3, "傷亡": 1, "拒測": 8, "隨時撤回": 1, "上限": 1, "小時制": 1, "逮捕到案": 2, "未核發": 1,
                "失敗": 1, "舉發期限": 1, "提審": 3, "法律扶助": 2, "同時是車主": 1, "搜索": ("cpc", 4), "無照": ("traf", 3)}
APP_ACTUAL = {"無照": ("traf", 4)}   # APP 道交條例分頁另含「應到案處所管轄說明」（rt-venue-guide）一則，實際 4 條
rows = []


def check(ok, area, item, detail=""):
    rows.append({"status": "PASS" if ok else "FAIL", "area": area, "item": item, "detail": str(detail)[:700]})
    print(("✅" if ok else "❌") + f" [{area}] {item}" + ("" if ok else f" — {str(detail)[:300]}"))
    return ok


def note(area, item, detail=""):
    rows.append({"status": "INFO", "area": area, "item": item, "detail": str(detail)[:700]})
    print(f"ℹ️ [{area}] {item} — {detail}")


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Quiet, directory=str(d)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/"


# ---------------------------------------------------------------- 靜態
def static_checks():
    A = "靜態"
    html = (HD / "index.html").read_text("utf-8")
    check(not re.search(r'href="[^"]*index\.html', html), A, "無任何連往 index.html 的連結（含「回快判助手」）", re.findall(r'href="[^"]*index\.html[^"]*"', html)[:3])
    check("serviceWorker" not in html, A, "未註冊 Service Worker（全檔不含 serviceWorker）")
    check('rel="manifest"' not in html and "apple-touch-icon" not in html, A, "無 manifest、apple-touch-icon 連結")
    check('<nav class="site-nav"' not in html and 'id="saCss"' not in html and "App 模式偵測" not in html, A, "無頁面切換列、底部膠囊樣式、App 模式偵測")
    body = re.sub(r"<style.*?</style>", "", html, flags=re.S)
    check("data-off-status" not in body and "data-share-url" not in body and "已有新版本" not in body, A, "無「離線資料」區塊、一鍵分享、更新提示")
    urls = re.findall(r"https?://[^\s\"'<>)]+", html)
    bad = [u for u in urls if not u.startswith(SITE) and u != "http://www.w3.org/2000/svg"]
    check(not bad, A, "無外部網址（只允許 og 使用的本站完整網址）", bad[:5])
    og = dict(re.findall(r'<meta property="(og:[a-z]+)" content="([^"]*)"', html))
    check(og.get("og:title") == "毒駕執法相關法規與實務彙編" and og.get("og:url") == SITE and og.get("og:image") == SITE + "img/icon-512.png"
          and (HD / "img" / "icon-512.png").is_file(), A, "og:title「毒駕執法相關法規與實務彙編」、og:url／og:image 為本網站完整網址且圖示存在", og)
    check('<meta name="robots" content="noindex, nofollow">' in html, A, "保留 noindex, nofollow")
    keys = set(re.findall(r'localStorage\.(?:getItem|setItem|removeItem)\(\s*"([^"]+)"', html))
    check(keys and all(k.startswith("handout-") for k in keys) and "localStorage.clear" not in html and "sessionStorage" not in html, A, "localStorage 只用 handout- 前綴的鍵、不用 sessionStorage", keys)
    srcs = re.findall(r'\ssrc="([^"]+)"', html)
    check(len([x for x in srcs if "/sop-" in x]) == 12 and all(x.startswith("./img/") and (HD / x[2:]).is_file() for x in srcs), A, "作業程序 12 張圖為 ./img/ 相對路徑且檔案存在", srcs[:3])
    check(' loading="lazy"' not in html, A, "作業程序圖片直接載入（不延遲）")
    check(not re.search(r'(?:href|src)="/(?!/)', html), A, "無以 / 開頭的根路徑")
    check("<header><small>©Johnson｜毒駕查處線上講義</small><h1>毒駕執法相關法規與實務彙編</h1>" in html, A, "頁首「©Johnson｜毒駕查處線上講義」＋「毒駕執法相關法規與實務彙編」")
    for w in ("hd-toc", "hd-key", "課程說明", "本章重點", "毒駕查處實務講義", "回目錄"):
        check(w not in html, A, f"H1.0 元素已刪除：{w}")
    for ref in ("origin/main", "main"):
        r = subprocess.run(["git", "show", f"{ref}:quiz.html"], cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            check(r.stdout == (ROOT / "quiz.html").read_bytes(), A, f"quiz.html 與 {ref} 逐字相同"); break
    else:
        check(False, A, "quiz.html 與 main 逐字相同", "找不到 main")
    changed = subprocess.run(["git", "diff", "--name-only", "origin/main", "--"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    changed += subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    check(all(f.startswith("handout/") for f in changed), A, "相對 main 只變更 handout/ 內檔案", changed)


# ---------------------------------------------------------------- 版面
JS_OVER = """() => { const cw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
  const wide = [...document.querySelectorAll('body *')].filter(e => { if (e.closest('#v-card, nav[role=tablist], .subnav')) return false; const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width && r.right > cw + 1 && s.position !== 'fixed' && s.visibility !== 'hidden' && e.offsetParent !== null; }).slice(0, 4).map(e => (e.className || e.tagName) + '「' + e.textContent.trim().slice(0, 10) + '」');
  return { cw, sw, wide }; }"""


def layout_tests(b, base):
    A = "版面"
    for w in (393, 360, 320, 1440):
        for dark in (False, True):
            tag = f"{w}px・{'深色' if dark else '淺色'}"
            ctx = b.new_context(viewport={"width": w, "height": 860}, device_scale_factor=1, color_scheme="dark" if dark else "light", is_mobile=w < 500, has_touch=w < 500)
            pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(base, wait_until="load"); pg.wait_for_timeout(400)
            bad = []
            for t in TABS:
                pg.locator(f"nav[role=tablist] button[data-t='{t}']").click(); pg.wait_for_timeout(250)
                r = pg.evaluate(JS_OVER)
                if r["sw"] > r["cw"] or r["wide"]:
                    bad.append((t, r))
                if t == "card":
                    pg.locator("#cardClose").click(); pg.wait_for_timeout(200)
            check(not bad, A, f"各分頁無水平溢出、無水平捲軸・{tag}", bad[:2])
            check(pg.evaluate("() => document.documentElement.classList.contains('dk')") == dark, A, f"外觀依系統{'深色' if dark else '淺色'}・{tag}")
            check(not errs, A, f"無 console error・{tag}", errs[:3])
            ctx.close()


# ---------------------------------------------------------------- 互動
def interaction_tests(b, base):
    A = "互動"
    ctx = b.new_context(viewport={"width": 393, "height": 860}, is_mobile=True, has_touch=True); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(base, wait_until="load"); pg.wait_for_timeout(400)
    names = pg.evaluate("() => [...document.querySelectorAll('nav[role=tablist] button')].map(b => b.textContent.trim())")
    check(names == TAB_NAMES, A, "分類頁籤：作業程序→刑事訴訟法→道交條例→刑法→其他法規→常見問題→速查卡→關於", names)
    for t in TABS:
        pg.locator(f"nav[role=tablist] button[data-t='{t}']").click(); pg.wait_for_timeout(300)
        vis = pg.evaluate("() => [...document.querySelectorAll('section.panel')].filter(p => !p.hidden).map(p => p.id)")
        sel = pg.evaluate("() => document.querySelector('nav[role=tablist] button[aria-selected=true]').dataset.t")
        check(vis == [f"p-{t}"] and sel == t, A, f"分類頁籤「{t}」可切換", {"visible": vis, "selected": sel})
        if t == "card":
            st = pg.evaluate("""() => new Promise(r => setTimeout(() => { const f = document.getElementById('cardFrame'), d = f.contentDocument;
                r({ shown: getComputedStyle(document.getElementById('v-card')).display !== 'none', pages: d ? d.querySelectorAll('.a4-page').length : 0, s: CZ.s, fit: CZ.fit }); }, 700))""")
            check(st["shown"] and st["pages"] == 2 and st["s"] > 0, A, "速查卡頁籤開啟全螢幕檢視（A4 兩頁）", st)
            pg.locator("#cardWrap").dblclick(position={"x": 150, "y": 200}); pg.wait_for_timeout(200)
            s2 = pg.evaluate("() => CZ.s")
            check(s2 > st["s"] * 1.5, A, "速查卡點兩下放大", {"before": st["s"], "after": s2})
            pg.locator("#cardWrap").dblclick(position={"x": 150, "y": 200}); pg.wait_for_timeout(200)
            check(abs(pg.evaluate("() => CZ.s") - st["fit"]) < 1e-6, A, "速查卡再點兩下還原")
            pg.locator("#cardClose").click(); pg.wait_for_timeout(250)
            check(pg.evaluate("() => cur") == "faq" and not pg.evaluate("() => document.documentElement.classList.contains('card-open')"), A, "速查卡「✕ 關閉」回到開啟前的分頁")
    # 主題小頁籤
    for t in ("cpc", "traf"):
        pg.locator(f"nav[role=tablist] button[data-t='{t}']").click(); pg.wait_for_timeout(250)
        n = pg.locator(f"#p-{t} .subnav button").count()
        okall = True
        for i in range(n):
            pg.locator(f"#p-{t} .subnav button").nth(i).click(); pg.wait_for_timeout(150)
            g = pg.evaluate("(t) => [...document.querySelectorAll('#p-' + t + ' .grp')].filter(x => !x.hidden).map(x => x.dataset.g)", t)
            okall &= g == [str(i)]
        check(n >= 2 and okall, A, f"「{t}」主題小頁籤 {n} 個皆可切換")
    # 摺疊（Q1～Q7）
    pg.locator("nav[role=tablist] button[data-t='traf']").click(); pg.wait_for_timeout(200)
    pg.locator("#p-traf .subnav button").first.click(); pg.wait_for_timeout(150)
    d = pg.locator("#rt-35-11-qa > summary"); d.scroll_into_view_if_needed(); d.click(); pg.wait_for_timeout(150)
    o1 = pg.evaluate("() => document.getElementById('rt-35-11-qa').open"); d.click(); pg.wait_for_timeout(150)
    o2 = pg.evaluate("() => document.getElementById('rt-35-11-qa').open")
    check(o1 is True and o2 is False, A, "摺疊（實務問答 Q1～Q7）可開合")
    # 法條互相跳轉：常見問題內的 Q 連結、網址 #錨點
    pg.locator("nav[role=tablist] button[data-t='faq']").click(); pg.wait_for_timeout(250)
    qj = pg.locator("a.qjump").first; target = qj.get_attribute("data-q"); qj.click(); pg.wait_for_timeout(700)
    top = pg.evaluate("(id) => Math.round(document.getElementById(id).getBoundingClientRect().top)", target)
    check(0 <= top <= 400, A, f"常見問題內連結跳到 {target}", top)
    for aid in ("rt-35-9", "cc-185-3", "cpc-88", "sop-note-10-2"):
        pg.goto(base + "#" + aid, wait_until="load"); pg.wait_for_timeout(700)
        r = pg.evaluate("(id) => { const e = document.getElementById(id); const p = e.closest('section.panel'); return { panel: p.id, hidden: p.hidden, top: Math.round(e.getBoundingClientRect().top) }; }", aid)
        check(not r["hidden"] and 0 <= r["top"] <= 400, A, f"#{aid} 跳轉到所在分頁並定位", r)
    # 作業程序：署頒／重點整理切換、12 張圖全部載入
    pg.goto(base, wait_until="load"); pg.wait_for_timeout(300)
    pg.locator("#p-sop .sub button[data-v='txt']").click(); pg.wait_for_timeout(150)
    a1 = pg.evaluate("() => [document.getElementById('v-pdf').hidden, document.getElementById('v-txt').hidden]")
    pg.locator("#p-sop .sub button[data-v='pdf']").click(); pg.wait_for_timeout(150)
    a2 = pg.evaluate("() => [document.getElementById('v-pdf').hidden, document.getElementById('v-txt').hidden]")
    check(a1 == [True, False] and a2 == [False, True], A, "作業程序「署頒正式版／重點整理」切換正常", [a1, a2])
    pg.wait_for_function("() => [...document.querySelectorAll('img[data-sop]')].every(i => i.complete && i.naturalWidth > 0)", timeout=30000)
    st = pg.evaluate("() => [...document.querySelectorAll('img[data-sop]')].map(i => [i.dataset.sop, i.naturalWidth > 0, i.classList.contains('pg-bad')])")
    check(len(st) == 12 and all(ok and not bad for _, ok, bad in st), A, "作業程序 12 張圖全部載入成功（無白圖）", st)
    check(not errs, A, "互動過程無 JavaScript 錯誤", errs[:3])
    ctx.close()
    # 圖片載入失敗：顯示可重試提示（不出現破圖）
    ctx = b.new_context(viewport={"width": 393, "height": 860}); pg = ctx.new_page()
    pg.route(re.compile(r".*/img/sop-03\.png.*"), lambda r: r.abort())
    pg.goto(base, wait_until="load")
    pg.wait_for_function("() => { const i = document.querySelector('img[data-sop=\"3\"]'); const s = i.parentNode.querySelector('.pg-st'); return s && /點此重試/.test(s.textContent); }", timeout=25000)
    vis = pg.evaluate("() => getComputedStyle(document.querySelector('img[data-sop=\"3\"]')).visibility")
    check(vis == "hidden", A, "圖片載入失敗時顯示「點此重試」且不顯示破圖")
    ctx.close()


# ---------------------------------------------------------------- 搜尋
JS_SEARCH = """(v) => new Promise(r => { const q = document.getElementById('q'); q.value = v; q.dispatchEvent(new Event('input'));
  setTimeout(() => { const per = {}; document.querySelectorAll('section.panel').forEach(p => { if (!p.hidden) per[p.id.slice(2)] = p.querySelectorAll('.art:not(.hide)').length; });
    const m = /共 (\\d+) 條/.exec(document.getElementById('sr').textContent); r({ total: m ? +m[1] : 0, per, sr: document.getElementById('sr').textContent }); }, 450); })"""


def counts(b, url):
    pg = b.new_page(); pg.goto(url, wait_until="load"); pg.wait_for_timeout(400)
    out = {k: pg.evaluate(JS_SEARCH, k) for k in SCRIPT_TABLE}
    pg.close(); return out


def search_tests(b, base, app_url):
    A = "講稿關鍵字"
    hd = counts(b, base)
    app = counts(b, app_url) if app_url else None
    table = []
    for k, want in SCRIPT_TABLE.items():
        h = hd[k]
        tab, n = want if isinstance(want, tuple) else (None, want)
        got = h["per"].get(tab, 0) if tab else h["total"]
        exp = APP_ACTUAL.get(k, want)
        etab, en = exp if isinstance(exp, tuple) else (None, exp)
        egot = h["per"].get(etab, 0) if etab else h["total"]
        if app:
            check(app[k] == h, A, f"「{k}」講義與 APP 搜尋結果完全相同（總數與各分頁條數）", {"講義": h["per"], "APP": app[k]["per"]})
        check(egot == en, A, f"「{k}」{'（' + tab + ' 分頁）' if tab else ''}條數 {en}", h["sr"])
        if got != n:
            note(A, f"「{k}」與講稿原表不同：講稿 {n}，APP／講義實際 {got}（以 APP 為準，請修改講稿）", h["sr"])
        table.append({"kw": k, "tab": tab, "script": n, "handout": got, "app": (app[k]["per"].get(tab, 0) if tab else app[k]["total"]) if app else None, "sr": h["sr"]})
    (OUT / "keyword_counts.json").write_text(json.dumps(table, ensure_ascii=False, indent=1), "utf-8")
    A = "?q= 參數"
    pg = b.new_page()
    for label, qs in (("URL 編碼", "?q=%E5%A7%8B%E5%BE%97"), ("未編碼", "?q=始得")):
        pg.goto(base + qs, wait_until="load"); pg.wait_for_timeout(600)
        r = pg.evaluate("() => ({ v: document.getElementById('q').value, sr: document.getElementById('sr').textContent, searching: document.body.classList.contains('searching') })")
        check(r["v"] == "始得" and r["searching"] and "共 3 條" in r["sr"], A, f"?q=始得（{label}）開啟即顯示結果、條數 3", r)
    pg.goto(base, wait_until="load"); pg.wait_for_timeout(400)
    r = pg.evaluate("() => ({ v: document.getElementById('q').value, searching: document.body.classList.contains('searching') })")
    check(r["v"] == "" and not r["searching"], A, "無參數時搜尋框為空、行為與原本相同", r)
    pg.close()
    return table


# ---------------------------------------------------------------- 與 APP 比對（--app）
def verbatim_tests(app_dir):
    A = "逐字比對"
    src = (app_dir / "regulations.html").read_text("utf-8"); out = (HD / "index.html").read_text("utf-8")

    def arts(h):
        d = {}
        for m in re.finditer(r'<article class="art[^"]*" id="([^"]+)"(.*?)</article>', h, re.S):
            t = re.sub(r'<p class="b2a">.*?</p>', "", m.group(2), flags=re.S)
            d[m.group(1)] = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", t))
        return d
    a, b = arts(src), arts(out)
    check(len(a) == 71 and a == b, A, "71 則條文（含函釋、常見問題、說明框）文字與 APP 相同", {"APP": len(a), "講義": len(b), "不同": [k for k in a if a.get(k) != b.get(k)][:5]})
    qa = lambda h: re.search(r'<details class="qa" id="rt-35-11-qa">.*?</details>', h, re.S).group(0)
    check(qa(src) == qa(out), A, "Q1～Q7 區塊與 APP 逐字相同")
    t = lambda h: re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", h))
    qc = (app_dir / "quick-card.html").read_text("utf-8")
    qc_pages = t(re.search(r'(<div class="a4-page".*)<script', qc, re.S).group(1))
    tpl = re.search(r'<template id="cardTpl">(.*?)</template>', out, re.S).group(1)
    tpl_pages = t(re.sub(r"<style.*?</style>", "", tpl[tpl.index('<div class="a4-page"'):], flags=re.S))
    check(qc_pages == tpl_pages, A, "速查卡全部文字與 APP quick-card.html 相同", {"APP": len(qc_pages), "講義": len(tpl_pages)})


SHOTS = [("sop", None), ("traf", None), ("faq", None), ("search", "拒測"), ("card", None)]
JS_LOOK = """() => { const pick = (s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    return [Math.round(r.left), Math.round(r.width), Math.round(r.height), c.backgroundColor, c.color, c.fontSize]; };
  return { header: pick('header'), h1: pick('header h1'), sbox: pick('#q'), tabs: pick('#tb'), tab1: pick('nav[role=tablist] button'), intro: pick('#p-sop .intro'), sub: pick('#p-sop .sub'), fig1: pick('#v-pdf figure') }; }"""


def compare_tests(b, base, app_url):
    A = "外觀對照"
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for w in (393, 1440):
        ctx = b.new_context(viewport={"width": w, "height": 860}, device_scale_factor=1, is_mobile=w < 500, has_touch=w < 500)
        pa, ph = ctx.new_page(), ctx.new_page()
        pa.goto(app_url, wait_until="load"); ph.goto(base, wait_until="load"); pa.wait_for_timeout(500); ph.wait_for_timeout(500)
        la, lh = pa.evaluate(JS_LOOK), ph.evaluate(JS_LOOK)
        # 位置以左緣、寬、高比較（APP 一般瀏覽器模式頁首上方多一列頁面切換列，講義已移除，故不比上緣）
        check(la == lh, A, f"{w}px：頁首、搜尋框、分類頁籤列、作業程序頁的左緣／寬／高／顏色／字級與 APP 相同",
              {k: (la[k], lh[k]) for k in la if la[k] != lh[k]})
        for t in (("traf", "faq") if w == 393 else ()):
            pa.locator(f"nav[role=tablist] button[data-t='{t}']").click(); ph.locator(f"nav[role=tablist] button[data-t='{t}']").click()
            pa.wait_for_timeout(300); ph.wait_for_timeout(300)
            js = "() => { const e = document.querySelector('nav[role=tablist] button[aria-selected=true]'); const r = e.getBoundingClientRect(), c = getComputedStyle(e); return [e.textContent, Math.round(r.width), Math.round(r.height), c.backgroundColor, c.color, c.fontSize]; }"
            check(pa.evaluate(js) == ph.evaluate(js), A, f"{w}px「{t}」分頁：選取中的頁籤樣式與 APP 相同", [pa.evaluate(js), ph.evaluate(js)])
        if w == 393 and Image:
            for name, kw in SHOTS:
                for p_, url in ((pa, app_url), (ph, base)):
                    p_.goto(url, wait_until="load"); p_.wait_for_timeout(450)
                    if name == "search":
                        p_.evaluate(JS_SEARCH, kw)
                    elif name == "card":
                        if p_ is ph:
                            p_.locator("nav[role=tablist] button[data-t='card']").click(); p_.wait_for_timeout(900)
                    else:
                        p_.locator(f"nav[role=tablist] button[data-t='{name}']").click(); p_.wait_for_timeout(450)
                a_png, h_png = OUT / f"_a_{name}.png", OUT / f"_h_{name}.png"
                pa.screenshot(path=str(a_png)); ph.screenshot(path=str(h_png))
                ia, ih = Image.open(a_png), Image.open(h_png)
                cv = Image.new("RGB", (ia.width + ih.width + 12, max(ia.height, ih.height)), "white")
                cv.paste(ih, (0, 0)); cv.paste(ia, (ih.width + 12, 0)); cv.save(OUT / f"compare_393_{name}.png")
                a_png.unlink(); h_png.unlink()
        ctx.close()
    note(A, "並排截圖：左為講義、右為 APP 法規頁（一般瀏覽器模式）；速查卡一張右側為 APP 法規頁首頁（APP 的速查卡在快判助手內）", "qa_output/compare_393_*.png")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--app", help="APP 原始檔目錄（regulations.html、quick-card.html、assets/）")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*"):
        f.unlink()
    static_checks()
    httpd, base = serve(ROOT); base += "handout/"
    app_httpd, app_url = None, None
    if args.app:
        app_dir = Path(args.app).resolve(); verbatim_tests(app_dir)
        app_httpd, app_url = serve(app_dir); app_url += "regulations.html"
    else:
        note("與 APP 比對", "未指定 --app：略過逐字比對、與 APP 搜尋結果並列、外觀對照（關鍵字條數仍依表檢查）")
    table = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            layout_tests(b, base)
            interaction_tests(b, base)
            table = search_tests(b, base, app_url)
            ctx = b.new_context(viewport={"width": 393, "height": 860}, is_mobile=True, has_touch=True); pg = ctx.new_page()
            for t in ("sop", "traf", "faq", "card"):
                pg.goto(base + "#" + t, wait_until="load"); pg.wait_for_timeout(900); pg.screenshot(path=str(OUT / f"393_light_{t}.png"))
            pg.goto(base + "?q=拒測", wait_until="load"); pg.wait_for_timeout(600); pg.screenshot(path=str(OUT / "393_light_search_拒測.png"))
            ctx.close()
            if app_url:
                compare_tests(b, base, app_url)
            b.close()
    finally:
        httpd.shutdown()
        if app_httpd:
            app_httpd.shutdown()
    npass = sum(r["status"] == "PASS" for r in rows); nfail = sum(r["status"] == "FAIL" for r in rows)
    (OUT / "report.json").write_text(json.dumps({"pass": npass, "fail": nfail, "keywords": table, "rows": rows}, ensure_ascii=False, indent=1), "utf-8")
    print(f"\n==== 結果：PASS {npass}｜FAIL {nfail} ====")
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
