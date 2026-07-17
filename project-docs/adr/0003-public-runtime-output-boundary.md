# 公開 repo runtime 的輸出邊界:脫敏升格為共用 sanitizer 層 + secret masking

> Status: **Accepted**(2026-07-18)。承 arch-review 2026-07-18(coord-vault
> `coordination/handoffs/fleet-medic-arch-review-2026-07-18.md`)finding #1
> (輸出洩漏面)與 #8b(ops-ro 通道)。決策由 Max 拍板(b+a)。

## Context

agent 與 sensor 住 off-box 的 GitHub Actions(ADR-0002),而本 repo 是**公開**的。
目前「脫敏由工具層保證」只覆蓋 `file_incident_report`。公開 runtime 因此有三個洩漏面:

- **Actions run logs 全世界可讀**:agent job 印出的任何工具輸出(tail_logs 的租戶
  log 尾、du 路徑、host 名)都會公開。
- **workflow artifacts 任何登入者可下載**:Run Ledger JSONL 按定義含**未脫敏**的
  完整工具輸出(脫敏只在 report 工具內)。
- artifacts 預設 **90 天過期**:ledger 同時是 eval 素材與 showcase 資產,會靜默蒸發。

## Considered Options

- **(a) 脫敏升格為共用輸出邊界層**(sanitizer module):ledger 寫入時就過,agent job
  的 step logging 只印脫敏後摘要。根治,但要一個新的邊界模組與紀律。
- **(b) 敏感常數註冊成 GitHub secret**(`OPS_BOX_HOST` 等):Actions 自動 mask log
  中出現的值。免費、即時,但只遮**完全比對**的值,不遮衍生/部分洩漏。
- **(c) runtime 拆到 private repo**,公開 repo 只放 curated replay。最安全,但與
  「面試載體要真 run」的決議有張力,且維運兩 repo 較重。**Rejected**(Max 裁決)。

## Decision

採 **b + a**:

1. **b(即時)**:`OPS_BOX_HOST` 等敏感常數註冊為 GitHub secret,拿到 Actions 免費的
   log masking 當第一道防線。
2. **a(根治)**:把脫敏從「report 工具的功能」升格為**共用 sanitizer 邊界層**。凡
   離開 box 進入任何公開面(Actions log / artifact / Run Ledger)的工具輸出,都必須
   先過這層;ledger 寫入即脫敏,agent step logging 只印脫敏摘要。`file_incident_report`
   與 #7 分支的 `redact.py` 是種子,落地時抽成 `ops_mcp/sanitize.py`。
3. runtime **維持公開**(不採 c),與「載體要真 run」相容。

## Consequences

- **sanitizer 是新的信任邊界**:與「安全不外包給模型」同位階——脫敏是工具/邊界層的
  確定性 code,不是 prompt 叮嚀。落點:sensor slice(step logging)、ledger slice
  (寫入即脫敏);由那兩片落地 `ops_mcp/sanitize.py` 並補失敗路徑測試。
- **secret masking 是防線之一非唯一**:只遮完全比對值;真正的邊界仍是 (a) 的 sanitizer。
- **ledger 保存**:artifacts 90 天過期 → ledger 兼具 eval/showcase 價值,需另存策略
  (保存期 / 匯出),留待 ledger slice 決定。
- **ops-ro SSH 通道約束(finding #8b)**:同屬「公開 repo runtime 安全邊界」主題的
  命令面。forced-command guard(`ops/ops-ro-guard`,已版控 + 測試)會把
  `SSH_ORIGINAL_COMMAND` 經 `sh -c` 重解析,且 `ssh -- <argv>` 先把 argv 用空白
  flatten 不加引號。故**送往受限唯讀 SSH 通道的指令不得含 shell metachar、不得有
  內嵌空白的參數**(`--format` 用 `::` 分隔而非 TAB;參數化的 service/id 先過工具內
  白名單)。這是讀工具正確性 + 安全的共同前提。

## 落地追蹤

- sanitizer 邊界層:sensor slice(#4)、ledger(loop slice #6 內)動工時落地。
- `OPS_BOX_HOST` 設為 secret:憑證/佈署收尾時做(與 #3 同批)。
- 通道約束:已於 `ops/ops-ro-guard` + read 工具(commit `bc57dab`)實作與測試。
