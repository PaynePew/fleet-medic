# fleet-medic

> 本地資料夾暫名 ops_agent(改名待檔案 handle 釋放);GitHub repo 正名 **fleet-medic**,公開(面試載體;脫敏由工具層保證)。

維運 agent:感測器發現 VPS fleet 異常時喚醒,用風險分層的工具診斷、閘門後修復、
行動後自我驗證、產出 incident report。自治權沿階梯升級,驗證失敗自動降級。

- 語彙:`CONTEXT.md`
- 架構:`project-docs/architecture/system-overview.md`
- 路線圖:`project-docs/roadmap.md`

狀態:Phase 0 完成(2026-07-11 grill 全數決議);Phase 1(disk-full tracer bullet)
於 Garmin 投遞後開工。

## Development

uv 專案,Python 3.12(見 `.python-version`)。

```sh
uv sync              # 裝 pytest + ruff(dev group)
uv run pytest        # 跑測試
uv run ruff check .  # lint
```

CI(`.github/workflows/ci.yml`)在每個 push/PR to `main` 跑 lint 與 test 兩腿。
