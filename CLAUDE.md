# fleet-medic

Runtime 維運 agent:確定性感測器發現 VPS fleet 異常時喚醒,agent 用風險分層的
MCP 工具帶診斷、閘門後修復、行動後自我驗證、產出 incident report。這是使用者的
**Agentic AI 學習主專案**——引導與解釋和產出同等重要,關鍵部位(agent loop)優先
讓使用者親手寫或緊密結對,不要全部丟給 subagent。

## 讀我之後先讀

1. `CONTEXT.md` — 語彙(Sensor/Tripwire/異常快照/Autonomy Ladder/白名單對/Run Ledger/Chaos Eval)。用這些詞,不要發明同義詞。
2. `project-docs/roadmap.md` — Phase 0-4、已全數決議的十條 open questions(含理由)。
3. `project-docs/architecture/system-overview.md` — 系統圖 + disk-full 時序 + JD 對映。
4. `project-docs/adr/` — 0001 感測與智能解耦(LLM 不進輪詢迴圈)、0002 off-box。

## 硬約束(違反=審查 FAIL)

- **LLM 不進輪詢迴圈**(ADR-0001):喚醒判斷永遠是確定性規則。
- **安全不外包給模型**:防呆(prune 不碰 in-use、脫敏、參數驗證)寫在工具內,
  不寫在 prompt 裡。
- 寫工具一律 dry-run 先行 + confirm token 兩段式;L2 閘門=GitHub Environment
  required reviewer。
- 預算三閘是確定性 code:per-incident $1(loop 內數 token)、日 $5(sensor 端)、
  eval 期另記。
- 感測器只答封閉問題;工具輸出一律有界(top-N/截斷)。

## 慣例

- Python + uv(workspace 慣例同 kbqabot);測試 pytest;TDD。
- 被管對象:`work/projects/live_sessions/platform` 的 VPS fleet(box 上動作一律
  經過 ops-mcp 工具,絕不裸 SSH 亂打)。
- Chaos eval 在 ephemeral demo box 上注入(reset.yml 可還原);「工具執行成功」
  不是驗證,重打 sensor 檢查綠了才是。
- 模式供應商 kbqabot:budget ledger、autonomy/rung ladder、獨立 Verdict、
  deploy/k8s 慣例可直接參考 `../knowledge_base_qa_bot`。
- Commit 慣例:conventional commits,無 AI attribution trailer。
