<div align="center">

# 🏔️ 山崖書院 shanya-shuyuan

### 把任何一本書，開成一門「認識你的課」

**先考後讀 ・ 人生鏡像 ・ 開卷兩分鐘**

**繁體中文** ・ [English](README.en.md)

</div>

---

> 這是一個 Claude Code / Codex **skill**，不是 app。agent 本身就是 runtime，HTML 就是課本——我們認為這是 agent 時代讀書該有的樣子。

## ✨ 為什麼是書院，不是又一個摘要工具？

### 🎯 先考後讀：課文為你的錯誤而寫
每堂課開場先出 3 題考你的**既有直覺**（不用讀書也能答）。答完，課文才生成——而且重心放在你答錯、答淺的地方；你已經會的，一筆帶過。學習科學站在這邊：提取練習勝過重讀。

### 🪞 雙欄人生鏡像：右欄是一個認識你的老師
左欄忠實保留書的精華（原句、故事、框架，細到可以不讀原書）；右欄把每個觀點對照到**你自己的人生**——用你說過的話、你的真實處境。並且有防造假鐵律：凡講你人生的宣稱，在你的個人檔案裡查無依據就刪；章節與你無關就老實說，不硬掰、不說教。

### ⚡ 開卷 ≤2 分鐘：你永遠不等系統
出題只需要目錄＋導論。你答題的時間，就是系統在背景備課（章節膠囊、個人鉤子、課綱重排）的時間。兩邊平行，死等歸零。

### 🎬 行動驅動：書要落地才算讀完
章末不是「反思問題」，是「本週一個可驗收的行動」——優先掛你真實待辦清單上的事。下堂課開場先驗收，沒做就聊聊卡在哪（這本身就是教材）。

### 🔒 隱私閘：個人資料永不上雲
個人脈絡包、右欄對照、學習紀錄全部只留本機。可選的 NotebookLM 音訊版只含書的內容。

## 🆚 跟其他方式差在哪

| | 書摘 app / AI 摘要 | 直接丟 NotebookLM 問 | **山崖書院** |
|---|---|---|---|
| 個人化 | ❌ 人人拿到同一份 | ⚠️ 要自己會問 | ✅ 課文為你的答案而寫 |
| 記得你學到哪 | ❌ | ❌ | ✅ learning-records＋ZPD 調難度 |
| 對照你的人生 | ❌ | ❌ | ✅ 雙欄鏡像＋防造假鐵律 |
| 讀完有行動 | ❌ | ❌ | ✅ 章末行動＋下堂驗收 |
| 開卷等待 | 即時但淺 | 上傳處理時間 | ✅ ≤2 分鐘出第一堂考題 |

## 🚀 快速開始

```bash
# 1. 裝進 Claude Code skills 目錄
git clone https://github.com/bockybocky/shanya-shuyuan.git ~/.claude/skills/shanya-shuyuan

# 2. 在 Claude Code 裡對你的 agent 說：
#    「把《某本書》開成課」（丟一個 epub 路徑）
#    之後用「繼續上課」「書院進度」推進
```

需要：Claude Code（或相容的 agent runtime）、Python 3.10+（拆書腳本，純標準庫）。可選：NotebookLM（膠囊 RAG＋音訊版）。

## 📖 一堂課長什麼樣

1. **驗收**上一堂的行動（第一堂跳過）
2. **先考 3 題**——直覺題，對話裡隨口答
3. 系統生成**雙欄課文 HTML**：左欄書、右欄你
4. 章末拿到**本週一個行動**
5. 學習紀錄自動落檔，下堂難度據此調

章序不照原書：按「與你的相關度 × 新資訊密度」重排，無關的章明講跳過。

## 🧩 架構與方法論

- 設計演化全程：[`references/design-journey.md`](references/design-journey.md)（含三個實戰事件怎麼改寫設計——「開卷 11 分鐘人都走了」是怎麼變成 ≤2 分鐘硬指標的）
- 拆書工具：[`scripts/epub_to_md.py`](scripts/epub_to_md.py)（epub → 逐章 MD，純標準庫、秒級、零 LLM）
- 上游致敬：[Matt Pocock 的 teach skill](https://github.com/mattpocock/skills)（教學法＋進度記憶）× [Garry Tan gbrain 的 book-mirror](https://github.com/garrytan/gbrain)（人生鏡像＋防造假紀律）

## ⚠️ 使用提醒

- 請用**你合法取得的書**。本工具不含任何書籍下載功能。
- 右欄品質取決於你的個人脈絡檔（CONTEXT_PACK）厚度——個人筆記越誠實，鏡子越準。

## 👥 作者

| | |
|---|---|
| [@bockybocky](https://github.com/bockybocky) | 設計與初版實作 |
| [@fredchu](https://github.com/fredchu) | 共同開發 |

## 授權

[MIT](LICENSE)

> [!TIP]
> ## 🎁 開源免費，誠摯歡迎回饋
> - ⭐ 好用請給個 Star
> - 💬 問題與想法歡迎開 [Issue](https://github.com/bockybocky/shanya-shuyuan/issues)
> - 🤝 歡迎 PR：批註收割式回流、PDF/OCR 支援、更多教學法變體
