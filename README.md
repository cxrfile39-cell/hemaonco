# 血液腫瘤期刊週報

依 ASCO（22 類）與 ASH（26 類）分類，每週一自動整理上一週（週一至週日，台北時間）新進入 PubMed 的文章。點標題直接開啟原文（DOI），可勾選要看的類別、勾選「保留」文章、自訂關鍵字。

資料來源：PubMed（NCBI, U.S. National Library of Medicine）。

## 第一次設定（約 10 分鐘）

1. **建立專案**：GitHub 右上角 **＋ → New repository**，名稱例如 `hemonc-weekly`，選 **Public**（免費帳號的 GitHub Pages 需要公開專案），按 **Create repository**。
2. **上傳檔案**：在新專案頁點 **uploading an existing file**，把解壓縮後資料夾裡的 `docs`、`scripts` 兩個資料夾和 `README.md` 拖進去，按 **Commit changes**。
3. **加入每週排程**：點 **Add file → Create new file**，檔名輸入 `.github/workflows/weekly.yml`（輸入斜線會自動變成資料夾），內容貼上本資料夾中 `.github/workflows/weekly.yml` 的全文，按 **Commit changes**。
   （若你的電腦能看到隱藏資料夾，也可以在第 2 步直接把 `.github` 一起拖進去，就不用這一步。）
4. **開啟網頁**：**Settings → Pages**，Source 選 **Deploy from a branch**，Branch 選 **main**、資料夾選 **/docs**，按 **Save**。
5. **產生第一期**：**Actions** 分頁 → 左側 **Weekly issue** → **Run workflow**。約 2–3 分鐘後完成。
6. 打開 `https://<你的帳號>.github.io/hemonc-weekly/` 就能看到。之後每週一 00:30（台北）會自動出新的一期。

### 補做以前的期數
在 **Run workflow** 的 date 欄填該週任一天（例如 `2026-11-10`），就會產生那一期。

## 自訂關鍵字

- **網頁上新增**：按「＋ 自訂關鍵字」，存在那台裝置的瀏覽器，打開時即時向 PubMed 查詢。
- **固定每週出刊、所有人都看得到**：編輯 `docs/panels.json` 最下面的 `custom`，例如：

```json
"custom": [
 {"id": "c-cml", "name": "CML 新藥", "query": "asciminib, ponatinib, olverembatinib", "scope": "core"}
]
```

`query` 可用逗號分隔關鍵字，或直接寫 PubMed 語法；`scope` 為 `core` 只搜精選期刊，`all` 搜全部 PubMed。`id` 每個面板要不同。

## 調整分類的查詢條件
每個分類的 PubMed 查詢寫在 `docs/panels.json` 的 `panels`，可直接修改關鍵字或期刊。

## 選用：NCBI API key
到 NCBI 帳號設定申請 API key，放到專案 **Settings → Secrets and variables → Actions → New repository secret**，名稱 `NCBI_API_KEY`。不設定也能運作，只是查詢較慢。

## 疑難排解
- **Actions 執行失敗、訊息含 `push` 或 `403`**：Settings → Actions → General → Workflow permissions 改為 **Read and write permissions**，再執行一次。
- 保留的文章與類別勾選存在各自裝置的瀏覽器；清除瀏覽器資料會一併清除。
