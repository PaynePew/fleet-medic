# Roadmap(working draft)

> 2026-07-11 起草於 grill 進行中。原則:**縱切優先**——每個 phase 結束時都有一個
> 「能跑完整迴圈」的東西,不蓋沒有消費者的橫向地基。時程刻意不填(quality over
> schedule;這是學習專案,投遞後至面試前為主要工作窗)。

## 已定案(grill 決議)

- **域:VPS 維運 agent**(live_sessions fleet)。備案 B(kbqabot Curator Agent,
  消費 kb_mcp 自動走 C9 鏈)已歸檔,若本專案窗口不夠或想要第二個小真跡再啟用。
- **Tracer bullet:disk-full incident**(真實案底 #453;診斷有真分支;修復低風險;
  可注入測試;驗證面客觀)。
- **喚醒模型:笨感測器 + tripwire 喚醒**(提案中,門檻 df>80%,學習期寧可多醒)。
- 工具包裝標準:**MCP**(`ops-mcp`),Claude Code 可直接掛 = 第一個免費客戶端。

## Phase 0 — Bootstrap

repo 建立、docs 骨架(本檔+架構圖)、grill 殘題收斂(見 Open Questions)、
CONTEXT.md 首批詞彙(Sensor / Tripwire / 異常快照 / Autonomy ladder / 白名單對)。

**Acceptance**:Open Questions 全部有決議或明確延後標記。

## Phase 1 — Tracer bullet:disk-full 縱切

- Sensor:cron shell/Python,查三個數字(df%、healthz、restart count),
  tripwire 附異常快照 spawn agent。
- ops-mcp v0:讀 `get_vitals / disk_breakdown / tail_logs / list_recent_deploys /
  read_runbook`;寫 `prune_images / rotate_logs`(dry-run 先行 + confirm token +
  內建防呆);報 `file_incident_report`(開 gh issue)。
- Agent loop:單 agent、tool-use 迴圈、run ledger(JSONL trace 落盤)。
- 起步自治級:**L1(提案)**,人工批准走到 L2。

**Acceptance(注入測試)**:在 ephemeral demo box 上人工塞爆磁碟(dd 大檔 +
垃圾 images),agent 端到端收斂:正確歸因 → dry-run 提案 → (批准後)執行 →
自我驗證綠 → incident report 內容經人工評分合格。**跑三種不同的塞法**
(大檔在上傳暫存 / superseded images / log 膨脹),歸因都要對——這就是
「診斷有真分支」的驗收。

**Prep notes / gotchas**:
- demo box 是 chaos lab:reset.yml 一鍵還原,注入不用怕。
- tool 輸出一律有界(top-N/截斷),否則 agent context 會被 log dump 塞爆。
- prune 防呆:永不碰 running containers 的 image;dry-run 與真執行是兩個呼叫。

## Phase 2 — 驗證與升級機制 + Showcase 包裝

- Chaos eval suite:把 Phase 1 的三種注入正式化成可重跑的 eval(場景庫 + 判分)。
- Autonomy ladder 落地:白名單(行動,條件)對、升降級規則、狀態持久化。
- run ledger 可讀化(incident 時間線視圖)。
- **Showcase 包裝(面試載體,不是可選項)**:README 首屏渲染好的架構圖(PNG,
  依 kbqabot 慣例)、一段 ≤3 分鐘可讀完的真實 incident run 回放、一份 incident
  report 樣本連結。設計假設:**面試官只給這個 repo 三分鐘**。

**Acceptance**:eval suite 全綠;一個(行動,條件)對真實走完 L1→L2→L3 升級;
人工觸發一次驗證紅,確認自動降級。

## Phase 3 — Multi-Agent 化 + 第二 incident 類

- **單 agent 跑通後才進場**(multi-agent 是手段不是目標)。
- 分離 diagnoser / remediator / verifier:verifier 是**獨立 context 的 agent**,
  只拿行動宣稱+系統實測,不拿 diagnoser 的推理(builder≠verifier≠merger 的
  runtime 版;防 confirmation bias)。
- 第二 incident 類:OOM crash-loop(含調參建議,診斷更「聰明」)。

**Acceptance**:同一 chaos suite 下,multi-agent 版的誤行動率 ≤ 單 agent 版;
verifier 至少抓到一次 remediator 的假成功(注入一個「看似修好」場景)。

## Phase 4 — 服務化 + AI Gateway 關切

- 感測器換成 alert webhook(uptime-kuma 或最小 Prometheus),agent 介面不變。
- Agent 自身的維運:model fallback(主模型掛→備援)、retry 策略、
  per-incident 預算上限(kbqabot budget ledger 模式移植)、k8s 部署
  (deploy/k8s 慣例沿用)。
- Observability:agent run 的 trace 面板。

**Acceptance**:拔掉主模型 API key,agent 在備援模型上仍收斂同一 eval;
單 incident 花費有硬上限且可觀測。

## Open Questions(grill 續行清單,依序)

1. ~~喚醒模型~~ **RESOLVED**:笨感測器 + tripwire(df>80% 起步,學習期寧可多醒)
2. ~~Agent loop 框架~~ **RESOLVED**:手寫 tool-use 迴圈,Python(uv 慣例同 kbqabot)。
   理由:loop 是全案唯一的本體知識,不外包;工具帶走 MCP 標準,belt 是資產、
   loop 是耗材;Phase 3 帶實戰經驗再評估框架。
3. ~~模型與預算~~ **RESOLVED**:Claude Sonnet 起手(tool-use 品質優先,學習訊號
   不被弱模型繞路汙染);三道確定性預算閘:per-incident $1(迴圈內數 token,
   超限=放棄+「預算耗盡」報告=一種 fallback 行為)、日上限 $5(sensor 端擋
   tripwire 風暴)、開發期 eval 預算另記 ~$20-30。跨供應商 fallback 留 Phase 4
   (比同供應商降級更硬的 AI Gateway 故事)。loop 成熟後把 eval 跑在 gpt-5-mini
   上做乾淨的模型對比(Phase 4 routing 素材)。
4. ~~Agent 部署位置~~ **RESOLVED**:GitHub Actions,Phase 1-2 連 sensor 一起住
   (scheduled workflow ~15min SSH 唯讀檢查,tripwire 同 workflow 接 agent job)。
   關鍵論證:**off-box 醫生**——disk-full 恰是會反殺 on-box agent 的 incident 類;
   一個活動部件、零新增憑證方向;Phase 4 長駐化(k8s+webhook)後 Actions 版降級為
   fallback 路徑(部署史=fallback 設計素材)。對 Q4 的修正:sensor 位置從
   「box 上 cron」改為「Actions 內」,誠實標記。
5. ~~憑證與最小權限~~ **RESOLVED**:兩把 SSH key——`ops-ro`(唯讀診斷,
   authorized_keys `command=` 前綴鎖死)、`ops-rw`(變更,存 GitHub Environment
   + required reviewer)。**L2 人類閘門直接借 GitHub Environment approval 實作**,
   不自建批准系統。gh token 用 fine-grained PAT(單 repo、issues:write)。
6. incident report 格式與去處(gh issue?repo 內 markdown?兩者?)
7. runbook 知識庫形式:純 markdown 檔 vs 重用 kbqabot 檢索模式
8. repo 命名(工作名 ops_agent)與公開性(public portfolio vs private)
9. ~~HITL 批准通道~~ **RESOLVED(隨 #5)**:GitHub Environment required reviewer
   = L2 閘門;批准動作、時間、批准人天然留痕。
10. B 備案(Curator Agent)是否在 Phase 2 後穿插做為第二真跡

## 與既有資產的關係

- **平台 repo**(`live_sessions/platform`):被管對象;sensor 可能住在它的
  部署慣例裡。
- **kbqabot**:模式供應商——budget ledger、rung ladder、Verdict 獨立驗證、
  ephemeral box、deploy/k8s 慣例全部移植;kb_mcp 是 ops-mcp 的結構前例。
- **coord-vault**:跨 session 協調慣例不變;本專案夠格開卡
  (長時程+人類閘門+跨專案依賴)。
