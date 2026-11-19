# 講義 PROGRESS（毒駕查處實務講義）

## H1.0 建立講義（已完成）
- 新增 `handout/index.html`（單一檔案，CSS／JS 內嵌、相對路徑）與 `handout/img/`；內容來源見 `SOURCE.md`。
- 單頁長捲動＋章節目錄；每章「回目錄」；手機 393／360／320px 與電腦寬畫面置中；淺色／深色。
- 「課程說明」「本章重點」為空白範本（`<div class="hd-fill">` 內的註解），填入內容後才會顯示。
- 列印：每章新頁、收合內容展開、互動元素隱藏、圖卡不切半；速查卡以具名頁面（A4、邊界 0）列印，剛好 2 頁。
- 驗收：`python handout/run_handout_qa.py`（Playwright；報告與截圖輸出至 `handout/qa_output/`，不納入版控）。

## 待辦
| # | 項目 | 說明 |
|---|---|---|
| 1 | APP 法規內容修正時同步修正講義 | APP 法規內容修正時（如刑法第185條之3 公布），須同步修正講義（本講義不與 APP 連動）。 |
| 2 | 填寫課程說明與各章本章重點 | 於 `index.html` 各 `<div class="hd-fill">` 內填寫；留空則不顯示。 |
| 3 | 確認講義網址 | 合併後確認 GitHub Pages 實際網址與 og:url／og:image 一致：https://johnsoneva0101-tech.github.io/Drugged-Driving-Pop-Quiz/handout/ |
