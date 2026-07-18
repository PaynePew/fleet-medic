# Coding Standards — fleet-medic

> **Freshness**: last reconciled through **ADR-0005** (2026-07-18). 若 `project-docs/adr/`
> 有比這個戳記更新的 Accepted ADR,本檔即為過期(drift)——依 §0.3 reconcile。

## §0 本檔制度(meta)

### §0.1 消費者與位階

- slice orchestrator(`project-docs/agents/orchestrator.js`)的 implement / review /
  verify prompts 以本檔為審查基準。
- CLAUDE.md「硬約束」節位階高於本檔一切規則;其審查條款化見 §1。

### §0.2 Reviewer-only(承 kbqabot ADR-0007 模式)

- 本檔是人類領地:sub-agent 只能 flag(以 finding 回報「本檔該補/該改」),
  不得直接編輯。
- 規則保持抽象:不引用具體檔名、路徑、行號——那些會腐爛;具體事實放 ADR 或 issue。

### §0.3 Freshness contract(reconcile + 戳記)

- 凡某 session 把一個 Accepted ADR 落地,**同一 session 內**必須 reconcile 本檔:
  把可通則化的教訓折進對應章節;若無可折,在 commit message 註明
  `nothing standard-worthy`。完成後把頂部 Freshness 戳記推進到該 ADR 編號。
- 過期判定:最新 Accepted ADR 編號 > 戳記編號 = drift。任何 session 發現 drift
  都要旗標並排入 reconcile,不得默默沿用過期規則。

## §1 硬約束(違反 = critical,擋 merge)

CLAUDE.md 硬約束的審查條款化;reviewer 逐條對照 diff:

- **LLM 不進輪詢迴圈**(ADR-0001):喚醒判斷/輪詢路徑出現任何模型呼叫 = critical。
- **安全不外包給模型**:防呆(prune 不碰 in-use、脫敏、參數驗證)必須是工具內
  確定性 code,且各有失敗路徑測試。只寫在 prompt 裡 = 未實作。
- **寫工具兩段式 + L2-gated apply**(ADR-0004):dry-run(讀,ops-ro)先產方案 + confirm
  token(= 方案 digest + TTL);apply 只在 L2-gated(Environment reviewer)job 內以 ops-rw
  執行,且**重驗前置**、方案漂移即拒;LLM 不與 ops-rw 同處。無/錯誤/過期 token 而能真執行,
  或 apply 走非 gated 路徑用寫金鑰 = critical。
- **box 特權經 guard 收斂**(ADR-0005):寫路徑碰 root-owned 資源時,特權(sudo)只在
  box 端 forced-command guard 內、對已審白名單 argv 施加;放大範圍 = 白名單那幾條命令(binary+flag+
  路徑前綴釘死),且 guard 在 sudo 前先擋 `..`/多路徑。把 sudo 開在 guard 外、或白名單放寬到未收斂
  的命令再 sudo = critical。被放行的命令**能否成功執行**只能靠真 box 驗(§4),注入 runner 的單元
  測試照不到權限洞。
- **工具輸出有界**:top-N / 截斷,且有測試斷言上界;無界輸出 = high。
- **預算閘是確定性 code**:per-incident 與日上限用 code 數 token/計次,
  不是 prompt 叮嚀;超限行為(放棄+報告)有測試。
- **Sensor 只答封閉問題**:往 sensor 加開放式判斷(診斷 if-else 樹之外的推理)
  = 漂移訊號,flag 之(ADR-0001 Consequences)。
- **公開面輸出脫敏**(ADR-0003):凡離開 box 進入公開面(Actions log / artifact /
  Run Ledger)的工具輸出,必須過共用 sanitizer 邊界層——脫敏是確定性 code,與「安全
  不外包給模型」同位階。只在單一報告工具脫敏、其餘公開面裸奔未過邊界層 = high。
- **L3 白名單條件是確定性謂詞**:入白名單的(行動,條件)對,其條件必須由工具/executor
  確定性重驗,模型只提名行動不自證條件成立(CONTEXT.md 白名單對不變量)。模型自證條件
  = 把租戶可控資料接上無人閘行動 = critical。

## §2 工具鏈

- uv 專用(deps / venv / 執行);pytest;ruff(掃過即綠才可 commit);Python 版本釘住。
- 尚無 typechecker(腳手架未引入);lint 閘 = ruff。引入 typechecker 需走 ADR。
- 新依賴:stdlib 或既有依賴能做的不加新依賴;要加,在 PR body 說明理由。

## §3 Correctness / 錯誤處理

- 失敗路徑優先於 happy path:空輸入、缺檔、SSH 斷線、malformed 工具輸出——
  未處理的案例是 finding。
- 不吞錯:不 swallow exception、不用預設值掩蓋呼叫方需要知道的失敗。
- 邊界驗證在邊緣(使用者輸入、SSH/shell 輸出解析、LLM 回應解析);內部呼叫互信。
- 送往受限唯讀 SSH 通道的指令必須 metachar-free、無內嵌空白參數(通道把 argv
  flatten 後經 `sh -c` 重解析;見 ADR-0003)——`--format` 類用非空白欄位分隔。
- 錯誤訊息要說「什麼壞了 + 什麼輸入/狀態導致」,單看 log 行可診斷。
- 失敗路徑也要清資源(context manager / try-finally 優於手動清理)。

## §4 測試

- TDD:每個行為變更先有一條會紅的測試(RED first)。
- 只測外部行為(公開 API / 工具呼叫邊界),不斷言私有狀態或 log 原文。
- 縫:SSH/shell 一律走 command-runner 注入點;LLM 一律走腳本化 client。
  真打 box 的驗證只存在於 chaos eval,不混進單元測試。
- 每個變更行為至少:一條 happy、一條 failure、一條 boundary;80% on changed code。
- 永不刪除或弱化既有測試來讓變更過;測試真的錯,在 commit message 明說。

## §5 命名 / 結構

- 用 CONTEXT.md 語彙命名(Sensor / Tripwire / Anomaly Snapshot / Run Ledger /
  Incident …),不發明同義詞。
- 名字說用途,不說做法;跟隨所改檔案既有慣例。
- 小單位:一個函式需要註解分段,就該是兩個函式。
- 註解只寫 code 無法表達的約束;不敘述下一行、不對 reviewer 喊話。

## §6 Git

- Conventional Commits(feat / fix / refactor / docs / test / chore / perf / ci);
  無 AI attribution trailer。
- 一 slice 一分支(`slice/issue-<n>`),從 main 開;merge ladder 語義見
  merge-autonomy 慣例(預設 Rung 0:分支備妥、人合)。
