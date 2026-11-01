# Movie_editing

剪片作品庫 — 每條剪好嘅片放一個位置，首頁自動列出，播放頁有章節時間碼。

## 目錄

```
index.html                首頁（作品卡 + 精選）
watch.html                播放頁（?v=<slug>）
assets/css/site.css       樣式
assets/js/app.js          首頁資料渲染
assets/js/watch.js        播放頁 + 章節
assets/data/edits.json    ← 所有作品資料（唯一要改嘅檔）
videos/                   成品 MP4
covers/                   封面圖
```

## 新增一條剪片

1. 成品轉 MP4（H.264 + AAC，yuv420p，`-movflags +faststart`）放入 `videos/`。
   單檔建議 < 50 MB；大過 100 MB GitHub 會拒收。
2. 封面 JPG 放入 `covers/`（16:9，1280×720）。
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
  "date": "2026-11-02",
  "tags": ["5 分鐘精華"],
  "featured": false,
  "chapters": [
    { "t": 0, "label": "開場" },
    { "t": 75, "label": "第二段" }
  ]
}
```

`featured: true` 嘅一條會上首頁大位（冇就自動用最新一條）。

## 本機預覽

```bash
python3 -m http.server 8000
# 開 http://localhost:8000
```

## 發佈

GitHub Pages：Settings → Pages → Source 揀 `main` / `root`。

## 作品

| 作品 | 長度 | 說明 |
| --- | --- | --- |
| 一個人的奧運：Eric the Eel | 5:01 | 由 8:07 原片剪成 18 段，5 分鐘敘事精華 |
