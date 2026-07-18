# 寫路徑的 ops-rw 接線:MCP 寫工具如何在 L2 閘門後拿到寫金鑰

> Status: **Accepted**(2026-07-18,Max 選 A)。承 #7 verify 的 HIGH(寫工具被接到
> ops-ro runner)+ arch-review 2026-07-18 #3(confirm token 綁定)。CODING_STANDARDS
> 戳記已同 session 推進到 ADR-0004(§0.3)。#7 據此建。

## Context

- ADR-0002:`ops-rw`(變更用金鑰)存 GitHub Environment `box-mutations` + required
  reviewer = 人(這就是 Autonomy Ladder 的 **L2 閘門**)。讀工具用 `_ssh_runner()`
  (`OPS_RO_SSH_KEY_PATH` / user `ops-ro`,`command=` 鎖死唯讀)。
- **問題**:#7 的 build 把寫工具(`prune_images`/`rotate_logs`)也接到 `_ssh_runner()`
  = ops-ro(verify HIGH)。這要嘛對 `command=`-鎖死的 ops-ro **失敗**,要嘛(若把 RO 變數
  指向寫金鑰)**繞過 L2 憑證閘**。ops-rw 只在「宣告 `environment: box-mutations`、被人
  批准過的 Actions job」內才拿得到 secret。
- **硬約束**:dry-run + confirm token 兩段式;L2 = Environment reviewer;安全不外包給模型。
  arch-review #3:token 應 = dry-run 方案 digest + TTL,apply 時工具**重驗前置**、方案漂移即拒。

核心設計題:**apply 時 ops-rw 只存在於被人批准的 gated job;dry-run 仍在一般 job(ops-ro)。
寫工具怎麼在那個 gated job 裡拿到 ops-rw runner——而且批准要綁到具體方案、LLM 別和寫金鑰同處?**

## 三方案共通的小改動(不管選哪個都要做)

- `server.py` 加 `_rw_ssh_runner()`(`OPS_RW_SSH_KEY_PATH` / user `ops-rw`),與 `_ssh_runner()`
  並存、惰性載入(沒設寫金鑰時列不出寫工具也不報錯)。
- 寫工具切兩段:**dry-run** = 只讀 box(ops-ro)算出方案 + 產 confirm token;**apply** = 用 ops-rw 執行。
- 差別全在:**apply 跑在哪個 job、LLM 在不在場、人的批准綁「跑 agent」還是「這份方案」。**

## Options

| 軸 | **B 單 job 雙 runner** | **A 兩 job・方案綁定** | **C 確定性 executor** |
|---|---|---|---|
| 做法 | agent job 直接掛 `environment: box-mutations`,MCP 同時持 ro+rw runner | agent job(ops-ro)dry-run 產方案+token 為 artifact → 另一 gated apply job 重新叫寫工具 apply(ops-rw)、用 token 重驗 | 同 A,但 apply job 跑**固定確定性 executor**(非 LLM、非完整 MCP),吃方案 artifact、重驗前置後套用;ops-rw 只活在它裡 |
| 複雜度 | 最低(一個 job) | 中(兩 job + artifact 傳方案) | 最高(方案 schema + 獨立 apply 入口) |
| L2 批准綁定 | 「**跑 agent**」(空白支票) | 「**這份 dry-run 方案**」(token) | 「**這份方案**」+ executor 再驗 |
| LLM 與 ops-rw | **同處**(整個 run 都握著寫金鑰) | 隔離(apply job 無 LLM) | 隔離(apply 連 MCP 都沒有) |
| 流程 | 人在 agent **診斷前**就得批准(倒置) | 診斷→提方案→人批→套用(順) | 同 A,套用端最笨最安全 |
| TOCTOU(#3) | 弱(同 job 無跨閘重驗誘因) | token digest+TTL+apply 重驗 | 最強(確定性重驗是本體) |
| 面試敘事 | 平 | 好(gated apply) | 最強(policy-as-code、人批具體 diff) |

## Recommendation

- **A 當 Phase 1 目標**:批准綁具體方案、LLM 與 ops-rw 隔離、複雜度可控,完整滿足硬約束 + #3。
- **C 當升級**:要最強安全故事 / Phase 2 policy-as-code 敘事時,把 apply 端從「MCP apply mode」
  換成獨立確定性 executor(增量不大,A 已把方案/token/重驗都備好)。
- **B 標為別走的捷徑**:雖最省事,但把 L2 弱化成「批准跑 agent」、讓模型全程與寫金鑰同處,
  與「安全不外包給模型 / L2 綁具體行動」相牴,不建議。

## 對 #7 build 的意義(選定後的 scope)

- 選 **A/C**:寫工具必須有明確的 **dry-run(方案 producer,只讀 ops-ro)/ apply(ops-rw)** 分離;
  定義**方案 schema**;token = 方案 digest + TTL;apply **重驗前置**、漂移即拒要求重 dry-run。
  apply 入口:A = MCP 的 apply 呼叫;C = `ops_mcp/apply.py` 確定性 executor。gated apply job 的
  workflow(`environment: box-mutations`)是薄薄一層。單元測試照 §4 用注入 runner,不打真 box。
- 選 **B**:寫工具用注入的 rw runner,workflow 只需一個掛 environment 的 job。

> 註:#7 可在 loop(#6)之前就建 + 單元測試(注入 runner);gated workflow 那層可最後接。

## Decision

- [x] **A（方案綁定）— 選定 2026-07-18(Max)**
- [ ] B（單 job,不建議）
- [ ] C（確定性 executor,最強/較重）

理由:批准綁具體 dry-run 方案、LLM 與 ops-rw 隔離、複雜度可控,完整對上硬約束 + #3。
C 保留為 Phase 2 policy-as-code 升級(A 已把方案 schema / token / apply 重驗都備好,增量小)。
