"""毒駕查處實務講義（handout/index.html）自動化驗收。

用法（於倉庫根目錄或 handout/ 內皆可）：python handout/run_handout_qa.py
需求：Python 3、Playwright（Chromium）。輸出：handout/qa_output/（報告、截圖、PDF；不納入版控）。
檢查：手機 393／360／320px 與電腦 1440px 不溢出且置中、目錄連結皆可跳轉、無 index.html 連結、無 Service Worker 註冊、
      無外部網址（og 本站網址除外）、localStorage 只用 handout- 前綴、quiz.html 與 main 逐字相同、
      列印：速查卡剛好 2 頁且兩種字型剩餘高度 ≥15px、作業程序圖卡不切半、每章新頁開始、收合內容展開、互動元素隱藏。
"""
import functools, json, re, socket, subprocess, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

HD = Path(__file__).resolve().parent
ROOT = HD.parent
OUT = HD / "qa_output"
SITE = "https://johnsoneva0101-tech.github.io/Drugged-Driving-Pop-Quiz/handout/"
FONTS = [("本環境字型", None), ("寬字型壓力測試", '"DejaVu Sans", "WenQuanYi Zen Hei", sans-serif')]
rows = []


def check(ok, area, item, detail=""):
    rows.append({"status": "PASS" if ok else "FAIL", "area": area, "item": item, "detail": str(detail)[:600]})
    print(("✅" if ok else "❌") + f" [{area}] {item}" + ("" if ok else f" — {str(detail)[:300]}"))
    return ok


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()


def serve():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/handout/"


def static_checks():
    A = "靜態"
    html = (HD / "index.html").read_text("utf-8")
    check(not re.search(r'href="[^"]*index\.html', html), A, "無任何連往 index.html 的連結", re.findall(r'href="[^"]*index\.html[^"]*"', html)[:3])
    check("serviceWorker.register" not in html and "serviceWorker" not in html, A, "未註冊 Service Worker（全檔不含 serviceWorker）")
    urls = re.findall(r"https?://[^\s\"'<>)]+", html)
    bad = [u for u in urls if not u.startswith(SITE)]
    check(not bad, A, "無外部網址（只允許 og 使用的本站完整網址）", bad[:5])
    og = dict(re.findall(r'<meta property="(og:[a-z]+)" content="([^"]*)"', html))
    check(og.get("og:title") == "毒駕查處實務講義" and og.get("og:url") == SITE and og.get("og:image") == SITE + "img/icon-512.png"
          and (HD / "img" / "icon-512.png").is_file() and og.get("og:type") == "website", A, "og:title／url／image 為本網站完整網址且圖示存在", og)
    check('<meta name="robots" content="noindex, nofollow">' in html and '<meta name="description"' in html, A, "具 noindex, nofollow 與 description")
    keys = set(re.findall(r'localStorage\.(?:getItem|setItem|removeItem)\(\s*"([^"]+)"', html))
    check(keys and all(k.startswith("handout-") for k in keys) and "localStorage.clear" not in html, A, "localStorage 只用 handout- 前綴的鍵", keys)
    for src in re.findall(r'\ssrc="([^"]+)"', html):
        check(src.startswith("./img/") and (HD / src[2:]).is_file(), A, f"圖片為相對路徑且檔案存在：{src}")
    check(not re.search(r'(?:href|src)="/(?!/)', html), A, "無以 / 開頭的根路徑")
    check("©Johnson" in html and "版</small><h1>毒駕查處實務講義</h1>" in html and 'var HANDOUT_VERSION = "115.11.19"' in html, A, "頁首「毒駕查處實務講義」＋「©Johnson 115.11.19版」")
    check("製作單位　花港刑警隊　許喬盛　警用電話 738-3630" in html, A, "頁尾署名「製作單位　花港刑警隊　許喬盛　警用電話 738-3630」")
    # quiz.html 與 main 逐字相同（本講義不修改隨堂測驗）
    for ref in ("origin/main", "main"):
        r = subprocess.run(["git", "show", f"{ref}:quiz.html"], cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            check(r.stdout == (ROOT / "quiz.html").read_bytes(), A, f"quiz.html 與 {ref} 逐字相同")
            break
    else:
        check(False, A, "quiz.html 與 main 逐字相同", "找不到 main")
    changed = subprocess.run(["git", "diff", "--name-only", "origin/main", "--"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    check(all(f.startswith("handout/") for f in changed), A, "相對 main 只新增／修改 handout/ 內檔案", changed)


JS_LAYOUT = """() => { const cw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
  const m = document.querySelector('.hd-main').getBoundingClientRect(), h = document.querySelector('.hd-head h1').getBoundingClientRect();
  const wide = [...document.querySelectorAll('.hd-main *')].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > cw + 1 && getComputedStyle(e).position !== 'fixed'; })
    .slice(0, 5).map(e => (e.className || e.tagName) + '「' + e.textContent.trim().slice(0, 10) + '」');
  return { cw, sw, left: Math.round(m.left), right: Math.round(cw - m.right), headL: Math.round(h.left), mainPad: parseFloat(getComputedStyle(document.querySelector('.hd-main')).paddingLeft), wide }; }"""


def layout_tests(b, base):
    A = "版面"
    for w in (393, 360, 320, 1440):
        for dark in (False, True):
            tag = f"{w}px・{'深色' if dark else '淺色'}"
            ctx = b.new_context(viewport={"width": w, "height": 860}, device_scale_factor=2 if w < 500 else 1, color_scheme="dark" if dark else "light",
                                is_mobile=w < 500, has_touch=w < 500)
            pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(base, wait_until="load"); pg.wait_for_timeout(400)
            r = pg.evaluate(JS_LAYOUT)
            check(r["sw"] <= r["cw"] and not r["wide"], A, f"無水平溢出・{tag}", r)
            check(abs(r["left"] - r["right"]) <= 2, A, f"內容置中（左右留白差 ≤2px）・{tag}", r)
            check(abs(r["headL"] - (r["left"] + r["mainPad"])) <= 1, A, f"頁首與內容左緣對齊・{tag}", r)
            check(pg.evaluate("() => document.documentElement.classList.contains('dk')") == dark, A, f"外觀依系統{'深色' if dark else '淺色'}・{tag}")
            check(pg.evaluate("() => getComputedStyle(document.getElementById('course')).display === 'none' && [...document.querySelectorAll('.hd-key')].every(k => getComputedStyle(k).display === 'none')"),
                  A, f"「課程說明」「本章重點」留空時不顯示・{tag}")
            check(not errs, A, f"無 console error・{tag}", errs[:3])
            if w in (393, 1440):
                t = "dark" if dark else "light"
                pg.screenshot(path=str(OUT / f"{w}_{t}_toc.png"))
                for cid in (("ch-sop", "ch-traf", "ch-card") if w == 393 else ("ch-sop",)):
                    pg.evaluate("(id) => document.getElementById(id).scrollIntoView()", cid); pg.wait_for_timeout(300)
                    pg.screenshot(path=str(OUT / f"{w}_{t}_{cid}.png"))
            ctx.close()


def toc_tests(b, base):
    A = "目錄跳轉"
    ctx = b.new_context(viewport={"width": 393, "height": 860}, is_mobile=True, has_touch=True); pg = ctx.new_page()
    pg.goto(base, wait_until="load"); pg.wait_for_timeout(300)
    links = pg.evaluate("() => [...document.querySelectorAll('#toc a')].map(a => [a.getAttribute('href'), a.textContent.trim()])")
    check(len(links) == 7, A, "目錄 7 章（作業程序→刑事訴訟法→道交條例→刑法→其他法規→常見問題→速查卡）", [t for _, t in links])
    for href, t in links:
        pg.goto(base, wait_until="load"); pg.wait_for_timeout(150)
        pg.locator(f'#toc a[href="{href}"]').click(); pg.wait_for_timeout(700)
        top = pg.evaluate("(id) => Math.round(document.getElementById(id).getBoundingClientRect().top)", href[1:])
        check(0 <= top <= 40 and pg.url.endswith(href), A, f"目錄「{t}」可跳轉", {"top": top, "url": pg.url})
        back = pg.locator(f'{href} .hd-chap-h .hd-back'); back.click(); pg.wait_for_timeout(300)
        check(abs(pg.evaluate("() => document.getElementById('toc').getBoundingClientRect().top")) <= 40, A, f"「{t}」回目錄鈕可返回目錄")
    # 頁內錨點（法條互相跳轉、Q1～Q7、分類群組）全部有對應 id
    anchors = pg.evaluate("() => [...document.querySelectorAll('a[href^=\"#\"]')].map(a => a.getAttribute('href').slice(1)).filter(h => !document.getElementById(h))")
    check(not anchors, A, "所有頁內錨點皆有對應目標", anchors[:5])
    pg.goto(base + "#rt-35-11-qa", wait_until="load"); pg.wait_for_timeout(400)
    check(pg.evaluate("() => document.getElementById('rt-35-11-qa').open"), A, "跳到 Q1～Q7（收合區塊）時自動展開")
    ctx.close()


JS_A4_SLACK = """() => [...document.querySelectorAll('.hd-card .a4-page')].map((p, i) => {
  const pr = p.getBoundingClientRect(), cs = getComputedStyle(p);
  const innerB = pr.bottom - parseFloat(cs.paddingBottom), innerR = pr.right - parseFloat(cs.paddingRight);
  const saved = []; p.querySelectorAll('.grow, .section-box').forEach(g => { saved.push([g, g.style.flex, g.style.justifyContent]); g.style.flex = '0 0 auto'; g.style.justifyContent = 'flex-start'; });
  const pj = p.style.justifyContent; p.style.justifyContent = 'flex-start';
  const kids = [...p.children].filter(k => getComputedStyle(k).position !== 'absolute');
  const slack = innerB - kids[kids.length - 1].getBoundingClientRect().bottom;
  saved.forEach(([g, f, j]) => { g.style.flex = f; g.style.justifyContent = j; }); p.style.justifyContent = pj;
  const wide = []; p.querySelectorAll('*').forEach(el => { const s = getComputedStyle(el); if (s.display === 'none' || s.position === 'absolute') return;
    const r = el.getBoundingClientRect(); if (r.width && r.right > innerR + 1) wide.push((el.className || el.tagName) + '+' + Math.round(r.right - innerR) + 'px'); });
  return { page: i + 1, slack: Math.round(slack * 10) / 10, sh: p.scrollHeight, ch: p.clientHeight, h: Math.round(pr.height * 10) / 10, wide };
})"""


def pdf_pages(path):
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?!s)", data))


def print_tests(b, base):
    A = "列印"
    ctx = b.new_context(viewport={"width": 1000, "height": 1200}); pg = ctx.new_page()
    pg.goto(base, wait_until="load"); pg.wait_for_timeout(500)
    pg.evaluate("() => document.fonts && document.fonts.ready")
    pg.emulate_media(media="print", color_scheme="light"); pg.wait_for_timeout(400)
    st = pg.evaluate("""() => ({ hidden: ['.hd-theme', '.hd-back', '.hd-jumps', '.hd-law .subnav', '.hd-foot'].map(s => [s, [...document.querySelectorAll(s)].every(e => getComputedStyle(e).display === 'none')]),
        details: [...document.querySelectorAll('details')].every(d => d.open),
        breaks: [...document.querySelectorAll('.hd-chap')].filter(c => c.id !== 'ch-card').map(c => [c.id, getComputedStyle(c).breakBefore]),
        figs: [...document.querySelectorAll('.hd-law figure.pg')].map(f => [getComputedStyle(f).breakInside, Math.round(f.getBoundingClientRect().height)]),
        cardPage: [...document.querySelectorAll('.hd-card .a4-page')].map(p => getComputedStyle(p).page), dk: document.documentElement.classList.contains('dk') })""")
    check(all(h for _, h in st["hidden"]), A, "列印隱藏回目錄鈕、外觀鈕、頁內跳轉鈕與分類按鈕、頁尾互動", st["hidden"])
    check(st["details"], A, "列印時收合內容（Q1～Q7）全部展開")
    check(all(v == "page" for _, v in st["breaks"]), A, "每章新頁開始（break-before: page）", st["breaks"])
    printable = (297 - 24) / 25.4 * 96
    check(len(st["figs"]) == 12 and all(bi == "avoid" and h <= printable for bi, h in st["figs"]), A,
          f"作業程序 12 頁圖卡不切半（break-inside: avoid，且每張高度 ≤ 可列印高度 {printable:.0f}px）", st["figs"])
    check(st["cardPage"] == ["qc", "qc"] and not st["dk"], A, "速查卡使用具名頁面 qc（A4、邊界 0）；列印改淺色", st)
    # 速查卡：兩種字型剩餘高度 ≥15px、無水平溢出、無內容超出
    slack = {}
    for fname, ff in FONTS:
        pg.emulate_media(media="screen"); pg.goto(base, wait_until="load"); pg.wait_for_timeout(300)
        if ff:
            pg.add_style_tag(content=".hd-card .a4-page, .hd-card .a4-page * { font-family: %s !important; }" % ff)
        pg.emulate_media(media="print"); pg.wait_for_timeout(400)
        for r in pg.evaluate(JS_A4_SLACK):
            slack[f"{fname}第{r['page']}頁"] = r["slack"]
            check(r["slack"] >= 15 and r["sh"] <= r["ch"] + 1 and not r["wide"], A, f"[{fname}] 速查卡第{r['page']}頁剩餘高度 ≥15px、不溢出", r)
    # PDF：全文與「只有速查卡」兩份；速查卡剛好 2 頁、全文 = 法規頁數 + 2
    pg.emulate_media(media="screen"); pg.goto(base, wait_until="load"); pg.wait_for_timeout(500); pg.emulate_media(media="print"); pg.wait_for_timeout(300)
    full = OUT / "handout_print.pdf"; pg.pdf(path=str(full), prefer_css_page_size=True, print_background=True)
    pg.add_style_tag(content="@media print{ .hd-head, .hd-toc, .hd-note, .hd-chap:not(#ch-card){ display:none !important } }")
    card = OUT / "handout_card_only.pdf"; pg.pdf(path=str(card), prefer_css_page_size=True, print_background=True)
    pg.goto(base, wait_until="load"); pg.wait_for_timeout(300); pg.emulate_media(media="print")
    pg.add_style_tag(content="@media print{ .hd-card{ display:none !important } }")
    law = OUT / "handout_law_only.pdf"; pg.pdf(path=str(law), prefer_css_page_size=True, print_background=True)
    n_full, n_card, n_law = pdf_pages(full), pdf_pages(card), pdf_pages(law)
    check(n_card == 2, A, "列印 PDF：速查卡剛好 2 頁（A4 正反面）", f"{n_card} 頁")
    try:
        from pypdf import PdfReader
        rd = PdfReader(str(full)); sizes = {(round(float(p.mediabox.width)), round(float(p.mediabox.height))) for p in rd.pages}
        tail = [rd.pages[i].extract_text() or "" for i in (-2, -1)]
        check(sizes == {(595, 842)}, A, "列印 PDF：每頁皆為 A4（595×842pt）", sizes)
        card_pages = [i + 1 for i, pp in enumerate(rd.pages) if "【正面】" in (pp.extract_text() or "") or "【背面】" in (pp.extract_text() or "")]
        check(card_pages == [len(rd.pages) - 1, len(rd.pages)] and "【正面】" in tail[0] and "【背面】" in tail[1], A,
              "列印 PDF（全文）：速查卡剛好占最後 2 頁（正面、背面），其他頁不含速查卡內容", {"總頁數": len(rd.pages), "速查卡頁": card_pages})
    except ImportError:
        print("（未安裝 pypdf：略過全文 PDF 逐頁檢查；速查卡頁數以「只印速查卡」PDF 為準）")
    ctx.close()
    return {"full": n_full, "law": n_law, "card": n_card, "slack": slack}


def main():
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*"):
        f.unlink()
    static_checks()
    httpd, base = serve()
    info = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            layout_tests(b, base)
            toc_tests(b, base)
            info = print_tests(b, base)
            b.close()
    finally:
        httpd.shutdown()
    npass = sum(r["status"] == "PASS" for r in rows); nfail = len(rows) - npass
    (OUT / "report.json").write_text(json.dumps({"pass": npass, "fail": nfail, "print": info, "rows": rows}, ensure_ascii=False, indent=1), "utf-8")
    print(f"\n==== 結果：PASS {npass}｜FAIL {nfail} ==== 列印：{info}")
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
