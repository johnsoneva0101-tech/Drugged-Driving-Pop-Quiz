# 講義內容來源（一次性複製，之後不連動）

- 來源倉庫：drugged-driving-assistant（毒駕快判助手 APP，私人倉庫）
- 來源 commit：`427ae47`（main，V1.4.6 合併後）
- 複製日期：115年11月19日
- **H1.1 改為「相關法規頁原樣搬遷」**：`index.html` 以 APP `regulations.html` 為主體原樣複製（頁首、精簡頂欄、搜尋、分類頁籤、主題小頁籤、摺疊、Q1～Q7、作業程序 12 張圖卡、深淺色、TOP 鈕、法條跳轉與所有樣式、互動），只移除離開 APP 無法運作的元素，並新增「速查卡」頁籤（內容取自 APP 速查卡母本 `quick-card.html`，互動比照 APP 快判助手速查卡分頁）與 `?q=關鍵字` 教學用搜尋。
- 圖片：`assets/sop-01.png`～`sop-12.png` → `img/`；`icons/icon-512.png`、`icon-180.png` → `img/`。
- 本講義為獨立 HTML，**之後不與 APP 連動**；APP 法規或速查卡內容修正時，須另行人工同步修正本講義（見 PROGRESS.md）。
