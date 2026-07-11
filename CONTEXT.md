# ops_agent

維運 agent 的語彙脈絡:一個被異常喚醒、用分層工具診斷與修復 VPS fleet、行動後自我驗證的 runtime agent。管的是「跑著的服務」,不是「專案的開發工作」。

## Language

**Sensor(感測器)**:
確定性、零 LLM 的定期檢查程序,量測 fleet 的少數關鍵數字(df%、healthz、restart count)。
_Avoid_: monitor、watcher、patrol agent(它不是 agent)

**Tripwire(絆線)**:
Sensor 內的一條門檻規則;越線即喚醒 Agent。門檻是設定值,不是模型判斷。
_Avoid_: alert(保留給 Phase 4 的外部告警系統)

**Anomaly Snapshot(異常快照)**:
Tripwire 觸發當下由 Sensor 打包的初始 context(當時的數字、容器表、log 尾巴)。是 Sensor 與 Agent 之間唯一的交接介面。
_Avoid_: payload、context dump

**Agent Loop(代理迴圈)**:
LLM tool-use 迴圈本體:讀快照、選工具、看結果、決定下一步,直到收斂或放棄。
_Avoid_: pipeline(本專案的反義詞)、workflow

**Tool Belt(工具帶)**:
Agent 可呼叫的工具開放集合,以 MCP 包裝(`ops-mcp`)。分讀(診斷)、寫(變更)、報(產出)三層。
_Avoid_: plugins、functions

**Dry-run**:
寫工具的第一段呼叫:只回報「將會做什麼、影響多大」,不改變系統。真執行是帶確認參數的第二次呼叫。

**Incident(事件)**:
一次 Tripwire 喚醒到 Agent 收斂(或放棄)的完整生命週期,以一份 Incident Report 收尾。
_Avoid_: task、job

**Incident Report(事件報告)**:
Agent 對一次 Incident 的結案文件:偵測 → 假設 → 行動 → 驗證 → 殘留風險。
_Avoid_: log、summary

**Verification(驗證)**:
變更動作後,Agent 重打 Sensor 同款檢查以確認 post-condition 成立。綠才算修好;「工具執行成功」不是驗證。
_Avoid_: confirmation、check(太弱)

**Autonomy Ladder(自治階梯)**:
L0 觀察 → L1 提案 → L2 閘門執行 → L3 白名單自治。升級靠戰績,任何驗證紅使該行動類降一級。
_Avoid_: permission levels、trust score

**Whitelist Pair(白名單對)**:
L3 自治的最小單位:(行動, 條件)的配對,而非行動本身。「在 df>80% 且無 running 容器受影響時 prune images」可入白名單;「prune」本身永遠不行。

**Run Ledger(運行帳)**:
Agent 每次運行的完整 JSONL 軌跡(工具呼叫、參數、結果、決策),落盤供回放與評分。
_Avoid_: trace log(口語可,文件用 Run Ledger)

**Chaos Eval(故障注入評測)**:
對 agent 的整合測試形式:在 ephemeral box 上人工製造故障,驗 Agent 端到端收斂與歸因正確。不是 mock LLM 回應。

**Fleet(艦隊)**:
被管對象:VPS 上的全部租戶服務 + edge。本 agent 的職權邊界=Fleet 的運行狀態。
_Avoid_: infra、servers
