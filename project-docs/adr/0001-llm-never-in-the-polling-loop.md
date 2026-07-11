# LLM 不進輪詢迴圈:感測與智能解耦

fleet-medic 的喚醒層是一個**確定性感測器**(scheduled workflow,SSH 唯讀量測 df% /
healthz / restart count),tripwire 越線才 spawn agent,並以**異常快照**(當下數字、
容器表、log 尾)作為兩層之間唯一的交接契約。Agent 永遠不輪詢世界。

原理的一般形式:**每一層放「能做出該層決策的最便宜元件」**。「有沒有事」是封閉問題
(可枚舉、可門檻化),交給 ≈$0 的規則;「是什麼事、怎麼辦」是開放問題(分支不可枚舉),
才值得召喚昂貴且非確定的 LLM。這不是 AI 時代的新發明——整個可觀測性產業
(Prometheus/Alertmanager/PagerDuty)都是「便宜規則持續評估,異常才 page 昂貴資源」;
過去那個昂貴資源是值班工程師,agent 接手的是工程師的椅子,不是 pager 的椅子。

## Considered Options

- **LLM 定期巡邏(rejected)**。三個獨立致命傷:(1) 經濟——15 分鐘一 tick 是每天
  96 次,其中 99%+ 資訊量為零,每月 $30-150 買不到任何東西;(2) 可測試性——「該不該醒」
  是安全關鍵決策,`if df > 80` 可寫回歸測試保證抓住每次越線,LLM 會把 87% 合理化成
  「偏高但趨勢穩定」,你永遠無法為它的警覺性寫出保證;(3) 可用性——耦合後,第三方
  API 的 uptime 成為偵測能力的上限。把不可測試的元件放上安全關鍵路徑,是本專案唯一
  真正禁止的事。
- **先蓋完整監控棧、alert webhook 喚醒(deferred,非 rejected)**。正規形態,但
  tracer bullet 會死在 yak shave 裡。Phase 4 以 webhook 換掉感測器時,異常快照契約
  不變,agent 一行不改——本 ADR 的解耦正是為了讓那次替換便宜。
- **只由人類召喚(rejected as 主軸)**。那是 copilot 不是 agent,autonomy 故事不成立。
  保留為旁路:同一個 agent 也可被人帶著問題召喚。

## Consequences

- 異常快照是兩層之間的唯一契約,兩側可獨立演化(sensor: cron→webhook→Prometheus;
  agent: 單體→multi)。
- 感測器必須保持笨:只答封閉問題。**漂移訊號(雙向)**——往 sensor 加診斷用
  if-else 樹=該交給 agent 了;agent 在重新推導可寫死的判斷(如比較兩個數字)=
  該下放給 sensor 了。
- 誠實的邊界:當訊號本身非結構化、無法門檻化(語義異常的 log、工單分診),模型
  就得進迴圈——但實務仍是**串聯(cascade)**:小模型/分類器當感測器,大模型在
  升級路徑。這是同一條原理向下遞迴一層,不是例外。
- tripwire 門檻(df>80%)是設定值:學習期刻意調鬆,誤喚醒是免費教材;每次誤喚醒
  的成本上限由預算閘(per-incident $1)保證。
