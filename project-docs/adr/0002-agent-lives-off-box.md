# Agent 住 off-box:醫生不與病人同床(GitHub Actions 起手)

fleet-medic 的 agent 本體與感測器在 Phase 1-2 都住在 GitHub Actions:scheduled
workflow(~15 分鐘)以唯讀 SSH key 量測 box,tripwire 觸發後同一 workflow 接續
agent job。Agent 不住在被它管理的 VPS 上。

核心論證是**故障域重疊**,而且本專案的 tracer bullet 把它變得具體:disk-full 恰恰
是會反殺 on-box agent 的 incident 類——磁碟滿的機器上,寫 log、開 process、載模型
回應都可能失敗;醫生病得跟病人一樣重。這是 SRE 舊智慧(「監控者不住在被監控的機器上」、
control plane / data plane 分離)的直接應用:Prometheus 從外部 scrape、k8s 重排死亡
節點的 controller 不能只活在該節點上、本 fleet 自己的 deploy.yml 也是從 Actions 外部
SSH 進 box。

## Considered Options

- **住 VPS 上(rejected)**。工具變本地呼叫、延遲最低,但:(1) 故障域重疊如上;
  (2) 小 box(512MB 級租戶)還要分資源給 agent 常駐。註:**升級 VPS 不改變此決策**
  ——論證是質性的(box 作為單一故障單元:kernel panic、供應商中斷、網路分割),
  不是量性的(資源不夠)。若要花錢,第二台小 box(獨立故障域,監控棧與 agent 的家)
  買到的架構多於一台大 box。
- **本機 / kind(rejected)**。筆電要開著,「內部服務」故事不成立;kind 留給部署
  練習與 Phase 4。
- **另租 VM(deferred)**。乾淨,但為 tracer bullet 加固定月費過早;Phase 4 長駐化
  時再評估(k8s 或第二 box)。

## Consequences

- 冷啟動 30-60s、Actions cron 粒度粗且會漂(~5-15 分鐘):對 disk-full 類綽綽有餘
  (磁碟不會 15 分鐘內從 60% 到 100%;會的話那是需要人的另一種事故)。**分鐘級敏感
  的 incident 類(healthz-red 立即回復)不得在 webhook 感測器就位前引入**——這是
  Phase 3+ 的前置依賴,記在 roadmap。
- 憑證方向單一:只有 GitHub→box 的 SSH(兩把:`ops-ro` command= 鎖死、`ops-rw` 存
  Environment + required reviewer),box 上不放任何回打 GitHub 的 token,洩漏面最小。
- L2 人類閘門直接借 GitHub Environment approval 實作:批准人、時間、內容天然留痕,
  不自建批准系統。
- Phase 4 agent 長駐化(k8s + webhook)後,Actions 路徑**降級為 fallback 而非刪除**
  ——主路徑掛掉時退回事件驅動的 Actions 版;部署演化史本身成為 fallback 設計的一部分。
