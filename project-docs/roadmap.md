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

**arch-review 2026-07-18 設計輸入(已 triage;細節見 coord-vault
`handoffs/fleet-medic-arch-review-2026-07-18.md`,決議 #1→ADR-0003)**:
- 公開面輸出脫敏(#1 / ADR-0003):離開 box 進 Actions log / artifact / Run Ledger 的
  工具輸出過共用 sanitizer 邊界層(不只 report 工具);`OPS_BOX_HOST` 設 GitHub secret 拿 log masking。
- 誰感測感測器(#4,sensor slice):sensor 每跑完 ping dead-man's switch(healthchecks.io 免費);
  公開 repo 的 scheduled workflow 60 天無活動自動停用,要盯——訊號缺席 ≠ 健康。
- tripwire 遲滯 + incident 去重(#5,sensor slice):spawn 前 `gh` 查同類 open incident 有則抑制
  (Actions 無狀態,issue 即免費狀態儲存);80 絆線、跌破 75 才重新武裝,防門檻震盪。
- Actions concurrency(#6,sensor slice):`concurrency` group + `cancel-in-progress: false`,
  防卡住的 agent run 與下一 tick 並行動同一 incident(一行 YAML)。
- confirm token 綁定(#3,寫工具 slice / #7):token = dry-run 方案摘要 digest + TTL,真執行時
  工具重驗前置條件、方案漂移即拒絕要求重 dry-run(防 dry-run→批准→執行的 TOCTOU 窗)。
- 批准空窗 vs 目標穩定性(#6,loop slice / 2026-07-18 #13 e2e 實證):dry-run→人批准→apply 這個模型
  隱含假設「目標在批准空窗內穩定」。confirm token 綁死 (service, log_path),所以兩種情況會**正確**
  drift 被拒:(a) token **串味**——拿別的 service 的 token 去 apply;(b) token **放久**——容器在空窗內
  被重建、log_path 變了。手動 dispatch 已實際踩到(mcp-server 兩次 drift;同一 shell 產 fresh token +
  即批准即過)。→ #6 的迴圈設計要吃這條:token 產生與 apply 在**同一段自動流程內、空窗最短化**;
  token↔service 綁定由 code 維護、不靠人手貼;drift 時**自動重 dry-run** 而非放棄(重 dry-run 是正常
  路徑,不是錯誤)。這也是「把人手空窗換成機器迴圈」本身的價值論證之一。
- 白名單條件不變量(#2):條件必須是工具內確定性重驗的謂詞,模型不自證——見 CONTEXT.md「白名單對」。
- prompt cache 紀律(#7,loop slice / Max 親寫):incident 內 system prompt 與 tool 定義 byte-stable、
  對話 append-only、快照放第一個 user message;per-incident $1 閘的實際 turn 容量取決於 cache 命中。
- eval 統計效力(#8a,Phase 3):「誤行動率 ≤ 單 agent」3 場景無統計效力,需場景庫擴充或多 seed 重跑。
- SSH host key(#8c):workflow 裡 pin host key(`accept-new` 在 ephemeral runner 上等於每次 TOFU)。
- ops-ro 通道約束(#8b / ADR-0003):forced-command guard 已入 repo 版控 + 測試(`ops/ops-ro-guard`);
  送往該通道的指令不得含 shell metachar、不得有內嵌空白參數。

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
6. ~~incident report~~ **RESOLVED**:gh issue 單一去處(一事件一 issue,label 標
   incident 類);固定五段:偵測→假設→行動(含 dry-run 證據)→驗證→殘留風險
   (五段=agent 輸出規格,eval 可對段落判分);run ledger JSONL 存 workflow
   artifact,issue 內放連結;**脫敏在 `file_incident_report` 工具內確定性執行**
   (IP/路徑/host 名;安全不外包給模型,例二)。
7. ~~runbook 形式~~ **RESOLVED**:Phase 1 純 markdown(`runbooks/disk-full.md`),
   `read_runbook(topic)`=讀檔;kb_mcp 檢索整合留 Phase 3+。
8. ~~repo 命名與公開性~~ **RESOLVED**:**fleet-medic**,公開(面試載體;
   脫敏由工具層保證)。本地資料夾改名待 handle 釋放。
9. ~~HITL 批准通道~~ **RESOLVED(隨 #5)**:GitHub Environment required reviewer
   = L2 閘門;批准動作、時間、批准人天然留痕。
10. ~~B 備案時機~~ **RESOLVED**:Phase 2 完成後再評估,不預先承諾。

> **Phase 0 驗收達成(2026-07-11)**:十條全數決議。Phase 1 於 Garmin 投遞後開工。

## 與既有資產的關係

- **平台 repo**(`live_sessions/platform`):被管對象;sensor 可能住在它的
  部署慣例裡。
- **kbqabot**:模式供應商——budget ledger、rung ladder、Verdict 獨立驗證、
  ephemeral box、deploy/k8s 慣例全部移植;kb_mcp 是 ops-mcp 的結構前例。
- **coord-vault**:跨 session 協調慣例不變;本專案夠格開卡
  (長時程+人類閘門+跨專案依賴)。
