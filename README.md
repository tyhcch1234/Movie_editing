# Movie_editing

剪片委託 + 作品庫。首頁上半係落單表單（Drive 連結、片長、背景音樂、通知 email），
下半係已完成作品，每條都可以播放同直接下載 MP4。

## 目錄

```
index.html                首頁（委託表單 + 作品庫）
watch.html                播放頁（?v=<slug>）
assets/css/site.css       樣式
assets/js/app.js          首頁：統計、精選、作品卡
assets/js/order.js        委託單：驗證、預覽、開 GitHub Issue、複製、下載 txt
assets/js/watch.js        播放頁 + 章節 + 下載
assets/data/edits.json    ← 所有作品資料（唯一要改嘅檔）
videos/                   成品 MP4
covers/                   封面圖
thumbs/                   章節截圖
```

## 落單流程（靜態頁嘅限制）

GitHub Pages 冇後端，所以表單唔會「自動剪片」。佢做三件事：

1. **送出委託** — 開一張已填好嘅 GitHub Issue（`tyhcch1234/Movie_editing`，label `edit-request`）。
   喺 GitHub 撳一下 `Submit new issue` 就存檔，之後可以用 API 讀取同關閉。
2. **複製委託單** — 一段格式化文字，直接貼落對話就即刻開工。
3. **下載 .txt** — 同一段文字存做檔案。

驗證規則：Drive 一定要 `drive.google.com` / `docs.google.com`；片長接受 `3:00`、`3`、`90s`、`2分30秒`，
範圍 0:20 – 30:00；YouTube 連結可留空（留空即由剪片方配免版稅音樂）；email 必填。

## 新增一條剪片

1. 成品轉 MP4（H.264 + AAC，yuv420p，`-movflags +faststart`），解析度跟素材，唔好 upscale放入 `videos/`。
   單檔必須 < 100 MB（GitHub 單檔上限）。
2. 封面 JPG 放入 `covers/`（16:9，1280×720，quality 75 左右，控制喺 300 KB 內）。
3. 喺 `assets/data/edits.json` 嘅 `edits` 陣列加一項：

```json
{
  "slug": "my-new-cut",
  "title": "作品名",
  "subtitle": "一句副標",
  "desc": "一兩句介紹。",
  "video": "videos/my-new-cut.mp4",
  "poster": "covers/my-new-cut.jpg",
  "duration": "4:32",
  "runtime": 272,
  "size": "48 MB",
  "date": "2026-11-02",
  "tags": ["4 分鐘精華"],
  "featured": false,
  "chapters": [{ "t": 0, "label": "開場" }]
}
```

- `featured: true` 會上首頁大位（冇就自動用最新一條）。
- `origin` 係選填：如果作品另有原版網頁，播放頁會多一個「原版頁」掣。
- 作品卡嘅「下載」用 `download` 屬性，所以要放喺同一個 repo（跨網域會被瀏覽器忽略）。

## 發佈

GitHub Pages：Settings → Pages → Source = `main` / `/ (root)`，push 之後幾十秒自動 rebuild。

**唔好**將 GitHub token 寫入任何網頁、JS 或者 commit；靜態頁嘅原始碼係全世界睇得到。
推送用本機 credential 或者一次性的 `x-access-token` remote。

## 本機預覽

```bash
python3 -m http.server 8000
# 開 http://localhost:8000
```

## 作品

| 作品 | 長度 | 說明 |
| --- | --- | --- |
| 一個人的奧運：Eric the Eel | 5:01 | 由 8:07 原片剪成 18 段，5 分鐘敘事精華 |
| 北潭涌：兩日一夜 | 3:00 | 97 條片段 + 相片剪成 3 分鐘營會片，原版頁 `/movie/pak-tam-chung/` 仍然保留 |
