# box 寫路徑的特權模型:guard 白名單命令如何取得 root 去動 docker log 檔

> Status: **Accepted**(2026-07-18,Max 選 1 + ops-ro 限定 sudo-du)。承 #13 端到端試跑
> 現形的權限洞。CODING_STANDARDS 戳記同 session 推進到 ADR-0005(§0.3)。

## Context

- #13 把 `ops-rw-guard` 裝上 box、`ops-rw` 金鑰 pin 到 guard 後,做端到端 apply 試跑,
  在 `rotate_logs` 的 dry-run 就掛掉:`du: cannot access
  '/var/lib/docker/containers/<id>/<id>-json.log': Permission denied`。
- 根因:`ops-ro`/`ops-rw` 是**非特權**帳號;docker 的 json log 檔在 `/var/lib/docker/containers/`,
  該目錄 `root:root drwx------`。非 root 讀不到 → dry-run 的 `du` 與 apply 的 `truncate`
  都碰同一堵牆。**rotate_logs 端到端跑不動。**(注:兩帳號能跑 `docker ps/inspect/images`
  是因為在 docker group 走 socket,那條路不碰檔案系統。)
- 這是注入 runner 的單元測試永遠照不到、只有真打 box 才現形的洞(CLAUDE.md:工具執行成功不是驗證)。
- guard 的**邊界**已對真 box 驗過(擋壞 argv、放行 docker ps、拒 quote 逃逸);**沒被驗到**的是
  「被放行的 du/truncate 能否成功執行」——答案是以非特權帳號不能。

核心設計題:**要讓 guard 白名單裡那幾條寫路徑命令(du 讀大小、truncate 清檔)能動 root-owned
的 docker log,特權從哪來——而且不把「安全靠 guard 收斂」這個既有姿態破壞掉?**

## Options

| 軸 | **1 guard 內限定 sudo** | **2 docker-as-root** | **3 群組/ACL** |
|---|---|---|---|
| 做法 | guard 對白名單的 du/truncate 改跑 `sudo -n <argv>`;box sudoers 只放行「這幾條 argv、限 `/var/lib/docker/containers/*`」的 NOPASSWD | 用 `docker run -v /var/lib/docker/containers:...:rw` 借 docker daemon 的 root 去動檔 | 把 docker log 檔/目錄以 setfacl 開給某 ops 群組讀寫 |
| 特權放大範圍 | = 已審 guard 白名單那幾條 argv(最小) | 一個能掛任意 host 路徑的 `docker run`(大) | 該群組對所有 container log 常駐讀寫 |
| 邊界仍在哪 | **guard 白名單**(不變) | guard 要放行 `docker run`+掛載形狀,難收斂 | 檔案權限(docker 重建容器會重置擁有權,得反覆補) |
| 與現況一致性 | 高:帳號本就在 docker group(≈ root-equiv),安全一向靠 guard 收斂 | 低:多一條 root 路徑 | 低:侵入 docker data dir |
| 脆弱性 | 低(sudoers argv 釘死 + guard 二次驗) | 中 | 高(擁有權漂移) |

## Decision

- [x] **1（guard 內限定 sudo）— 選定 2026-07-18(Max)**
- [ ] 2（docker-as-root,不建議)
- [ ] 3（群組/ACL,不建議)

具體:

- **`ops-rw-guard`**:`du -b /var/lib/docker/containers/…` 與 `truncate -s 0 /var/lib/docker/containers/…`
  兩條白名單分支,exec 前把命令改為 `sudo -n <原命令>`。docker 命令(ps/inspect/images/image rm)
  走 socket、**不加 sudo**。
- **`ops-ro-guard`**:新增 `docker images ` 到白名單(解鎖 `prune_images` dry-run,它讀 `docker images`);
  並把 **containers-path 的 `du`** 分支(且僅這條)改跑 `sudo -n`,同時補「恰一個路徑 + 無 `..`」的檢查
  ——因為加了 sudo,原本寬鬆的 `du ` 前綴若不收緊,`sudo du … /etc/shadow` 這種第二路徑會以 root 讀任意檔。
  一般 `du`(disk_breakdown 的 `du -x -b --max-depth=2 /`)維持**不加 sudo**。
- **ops-ro 給 sudo-du 的取捨**(子決策,Max 選給):dry-run 的 `du` 給 ops-ro 限定 sudo,好處是 dry-run
  能顯示 `reclaim_bytes` 供人判斷是否批准;代價是「唯讀安全鍵」略微放寬(能以 root `du` containers-path)。
  範圍極窄(單一 binary、單一路徑前綴、guard 再收斂),換到的批准資訊值得。
- **box sudoers**(版控於 `ops/sudoers.d/fleet-medic-ops`,裝到 `/etc/sudoers.d/`,mode 440):
  `ops-ro` → `NOPASSWD: /usr/bin/du -b /var/lib/docker/containers/*`;
  `ops-rw` → 上句 + `/usr/bin/truncate -s 0 /var/lib/docker/containers/*`。

## Consequences

- **安全邊界不變**:真正決定「能跑什麼」的仍是 guard 白名單;sudoers 是第二層收斂(binary + flag + 路徑前綴釘死)。
  guard 的 `..` 拒絕在 sudo 之前跑,擋掉 sudoers `*` 萬用字元會跨 `/` 的已知行為。
- **可測範圍**:guard 的**決策**(哪條放行、哪條加 sudo、哪條擋)用 check-mode 單元測試 pin;
  sudo 真的取得 root **只在真 box 驗**(重跑 #13 e2e),同 §4「真打 box 只在 chaos/實跑」。
- **升級路**:若日後要更緊,ADR-0004 的 C 案(獨立確定性 executor)可把 sudo 範圍再縮到單一入口。
- **待辦**:部署新 guard + sudoers 到 box → 重跑 #13 端到端 → 過了關 #13。
