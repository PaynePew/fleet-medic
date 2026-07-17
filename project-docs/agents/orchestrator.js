export const meta = {
  name: 'fleet-medic-slices',
  description: 'fleet-medic 專案版 slice orchestrator:plan(GitHub issues 或明確 slices)→ 每 issue 並行 build(implement+review 同 worktree)→ 對抗驗證(嚴重度閘門)→ 過閘門才 merge(預設只備妥分支)',
  phases: [{ title: 'Plan' }, { title: 'Build' }, { title: 'Merge' }],
}

// fleet-medic 客製自全域 slice-orchestrator(2026-07-11 版)。差異:
//   - promptsDir / standards 指向 repo 內檔案(repo-relative,worktree 內可讀)
//   - commit 慣例:Conventional Commits(prompts 內已改,不再用 RALPH: 前綴)
//   - 預設 Rung 0 語義:autoMerge:false,分支只備妥,人合(merge-autonomy ladder)
// invoke:Workflow({ scriptPath: 'project-docs/agents/orchestrator.js', args: {...} })

// ── args 容錯:物件 OR(誤傳的)JSON 字串都吃,避免覆寫被 typeof 守衛靜默吞掉 ──
const _argsObj = typeof args === 'string'
  ? (() => { try { return JSON.parse(args) } catch { return {} } })()
  : (args && typeof args === 'object' && !Array.isArray(args) ? args : {})

// ── 設定(用 args 覆寫,例:{ only:['5'], autoMerge:false })──
// 來源優先序:slices(明確清單,零 tracker) > only+skipPlan(明確 id,零 tracker) > gh issue list
const CONFIG = {
  promptsDir  : 'project-docs/agents/prompts',
  standards   : 'project-docs/CODING_STANDARDS.md',
  branchPrefix: 'slice/issue-',
  baseBranch  : 'main',   // build 從這裡開分支(帶上已 merge 的依賴 + ADR);用 args 覆寫整合目標
  adversarial : true,     // 安全預設:對抗驗證開(只擋 critical/high)
  autoMerge   : false,    // 安全預設:只備妥分支,等人合;要自動合傳 {autoMerge:true}(需使用者具名授權)
  slices      : null,     // 明確切片清單 [{id,title,branch?}];給了就用它當來源,完全不碰任何 tracker
  only        : null,     // 只做這些 id(gh 來源時當過濾;配 skipPlan 時當明確來源)
  skipPlan    : false,    // 配 only:跳過 gh 查詢,直接 build
  ..._argsObj,
}
const MODELS = { plan:'haiku', build:'sonnet', verify:'opus', merge:'opus', note:'haiku', ...(_argsObj.models ? _argsObj.models : {}) }

// 開跑就印出「實際生效」的設定——萬一覆寫沒套進去,第一行就現形(不再靜默跑預設)
log(`effective config → slices=${CONFIG.slices ? CONFIG.slices.length : 'null'} · only=${JSON.stringify(CONFIG.only)} · adversarial=${CONFIG.adversarial} · autoMerge=${CONFIG.autoMerge} · base=${CONFIG.baseBranch} · standards=${CONFIG.standards}`)

const PLAN_SCHEMA = { type:'object', required:['issues'], properties:{
  issues:{ type:'array', items:{ type:'object', required:['id','branch'], properties:{
    id:{type:'string'}, title:{type:'string'}, type:{type:'string'}, branch:{type:'string'} } } } } }
const VERDICT_SCHEMA = { type:'object', required:['verdict','blockers'], properties:{
  verdict:{ type:'string', enum:['pass','changes-requested'] },
  blockers:{ type:'array', items:{ type:'object', required:['severity','evidence'], properties:{
    file:{type:'string'}, line:{type:'number'}, issue:{type:'string'},
    evidence:{type:'string'},   // 必填:怎麼確認是真的(測試輸出/重現步驟/diff 具體行為);逼 reviewer 拿證據,防「一定找得到東西」式的湊 blocker
    severity:{ type:'string', enum:['critical','high','medium','low'] } } } } } }

const mkBranch = (id) => CONFIG.branchPrefix + String(id).replace(/[^A-Za-z0-9._-]/g, '-')

// build:同一 worktree 內 從 baseBranch 開分支 → implement → 自我精簡
const buildPrompt = (i) => `你在一個隔離 git worktree 內,獨自負責 issue ${i.id}(${i.title || 'untitled'})。
重要:worktree 預設可能停在過時 base(origin/${CONFIG.baseBranch}),務必先從本地 ${CONFIG.baseBranch} 開分支,才帶得上前面已 merge 的依賴與 ADR。
1) 從 ${CONFIG.baseBranch} 開新分支:git switch -c ${i.branch} ${CONFIG.baseBranch}
2) 實作:讀 ${CONFIG.promptsDir}/implement.md 照做。代入 {{ISSUE_ID}}=${i.id}、{{ISSUE_TITLE}}=${i.title || ''}、{{BRANCH}}=${i.branch}、{{STANDARDS}}=${CONFIG.standards}。遵守與你所改檔案相關的 Accepted project-docs/adr/* 與 CONTEXT.md。
3) 自我精簡:再讀 ${CONFIG.promptsDir}/review.md 照做(對你的改動 in-place 精簡並 commit)。
範圍紀律:只動這片需要的檔;絕不刪除/還原其他 slice 的成果、不刪 ADR/CONTEXT/CODING_STANDARDS、不刪既有測試。
防污染護欄(違反即視為失敗):絕不 git init / 初始化任何 issue tracker、絕不新增 tracker/agent 鷹架(.beads/.agents/.codex/AGENTS.md)、絕不 commit 或改動 CLAUDE.md / .claude/settings.json / .gitignore。
回傳:改了哪些檔、git diff ${CONFIG.baseBranch}...${i.branch} 檔案清單、ruff/pytest 是否全綠。`

// verify:獨立、唯讀;嚴重度標記,只有 critical/high 擋 merge
const verifyPrompt = (i) => `唯讀對抗式驗證 issue ${i.id}:執行 git diff ${CONFIG.baseBranch}...${i.branch}(三點:只看這片相對 merge-base 的改動,不會把 base 在本片 fork 後新增的 commit 誤判成本片的「刪除/還原」),找「影響正確性、安全性或明確需求」的 bug,並對照 ${CONFIG.standards} 與相關 Accepted ADR 檢查違規。CLAUDE.md 的「硬約束」節違反=critical。
範圍紀律(precision over recall):只回報有真實影響的 finding;風格偏好、假設性重構、與這片需求無關的改進建議一律不報。每個 blocker 必附 evidence——用具體管道證明(測試輸出、實際執行的回應、diff 中的具體行為);給不出證據的疑慮最高只能標 medium。
若 diff 顯示它刪除/還原了既有成果(其他 slice、ADR、基礎設施),或新增了 .beads/.agents/.codex/AGENTS.md、動了 CLAUDE.md / .claude 設定(越界污染),標 critical(多半代表 base 拿錯或 agent 越界),evidence 寫出 diff 裡的具體檔案。
每個 blocker 標 severity:critical/high=會壞/不安全/違反硬約束/刪到別人成果(擋 merge);medium/low=小毛病(回報不擋)。
不要改 code、不要 commit。回 verdict(pass=無 critical/high;否則 changes-requested)與 blockers(file,line,issue,severity,evidence)。`

// note:build+verify 完成後,若該 slice 是 GitHub issue(數字 id),把 implementer 摘要 + reviewer 結論貼成 issue 留言;否則此步整段略過。不改 code、不 commit。
const commentPrompt = (i, r) => `你的唯一任務:把 slice ${i.id} 的階段成果貼成對應 GitHub issue 的留言,寫完即止——不要改任何檔案、不要 commit、不要 close。
分支:${i.branch}
執行一筆 gh issue comment ${i.id}(內容含特殊字元時用 --body-file - 從 stdin 餵入,避免 shell 解析):

=== IMPLEMENTER ===
${String(r?.build ?? '(無摘要)').slice(0, 2000)}
=== /IMPLEMENTER ===
=== REVIEWER ===
verdict=${r?.v?.verdict ?? 'n/a'};擋 merge 的 blocker ${(r?.blocking ?? []).length} 個。
${JSON.stringify((r?.blocking ?? []).map(b => ({ file: b.file, line: b.line, severity: b.severity, issue: String(b.issue ?? '').slice(0, 200) })), null, 2)}
(evidence 欄位刻意不貼:reviewer 的 evidence 可能含 exploit payload / 逐步重現,而 GitHub issue 是公開的——敏感細節留在 orchestrator 回傳與私下報告,不外洩到公開 repo。)
=== /REVIEWER ===

只貼這一筆,不要做其他事。`

// merge:批次、跑一次,合進 baseBranch
const mergePrompt = (list) => `讀 ${CONFIG.promptsDir}/merge.md 照做,合併進 ${CONFIG.baseBranch}。代入:
{{BRANCHES}}=${list.map(i => i.branch).join(' ')}
{{ISSUE_IDS}}=${list.map(i => i.id).join(' ')}
回傳合併與關閉結果。`

// ── ① PLAN:明確 slices / only(零 tracker)優先;否則 gh issue list(GitHub 原生佇列)──
let todo
if (CONFIG.slices?.length) {
  todo = CONFIG.slices.map(s => ({ id:String(s.id), title:s.title || '', type:s.type || 'task', branch: s.branch || mkBranch(s.id) }))
  log(`明確 slices:直接做指定的 ${todo.length} 片(不查任何 tracker)`)
} else if (CONFIG.skipPlan && CONFIG.only?.length) {
  todo = CONFIG.only.map(id => ({ id:String(id), title:'', type:'task', branch: mkBranch(id) }))
  log(`skipPlan:直接做指定的 ${todo.length} 個 id(不查任何 tracker)`)
} else {
  phase('Plan')
  const plan = await agent(
    `執行 gh issue list --state open --limit 100 --json number,title,labels 取得目前開著的 GitHub issue(不要自己推依賴)。
排除帶有 'epic'、'prd' 或 'ready-for-human' label 的(PRD/容器不是切片;ready-for-human 是使用者親手做的片,絕不代工)。
再對每個候選查 gh api repos/{owner}/{repo}/issues/{n} --jq .issue_dependencies_summary.blocked_by,>0(有開著的 blocker)的排除——依賴未合的片不能開工。
把每筆整理成 {id, title, type, branch}:id = issue number 的字串、branch = "${CONFIG.branchPrefix}" + id。只回傳 open、非 epic/prd、非 ready-for-human、無開著 blocker 的。
若這個 repo 沒有 GitHub remote 或 gh 未認證而無法列 issue,回 {issues: []}(不要報錯,讓 orchestrator 提示改用明確 slices)。`,
    { label: 'plan(gh issue list)', phase: 'Plan', schema: PLAN_SCHEMA, model: MODELS.plan })
  todo = (plan?.issues ?? []).filter(i => i.type !== 'epic')   // 程式層硬擋:就算 agent 漏看,epic 也絕不進 build
  if (CONFIG.only) todo = todo.filter(i => CONFIG.only.map(String).includes(i.id))
}
if (!todo.length) { log('沒有可並行的 issue(傳 {slices:[...]} 或 {only:[...],skipPlan:true} 明確指定,或先開/解鎖 GitHub issue)'); return { planned: 0 } }
log(`要做 ${todo.length} 個 issue:${todo.map(i => i.title ? `${i.id}(${i.title})` : i.id).join(', ')}`)

// ── ② BUILD(每 issue 並行;build=implement+review 同 worktree、verify 獨立唯讀且嚴重度閘門、note 把成果貼回 GitHub issue)──
phase('Build')
const lbl = (i) => i.title ? `${i.id} · ${i.title}` : i.id
const built = await pipeline(
  todo,
  (issue)     => agent(buildPrompt(issue), { label:`build:${lbl(issue)}`, phase:'Build', isolation:'worktree', model: MODELS.build }),
  (b, issue)  => CONFIG.adversarial
    ? agent(verifyPrompt(issue), { label:`verify:${lbl(issue)}`, phase:'Build', schema: VERDICT_SCHEMA, model: MODELS.verify })
        .then(v => ({ build: b, v, blocking: (v?.blockers ?? []).filter(x => x.severity === 'critical' || x.severity === 'high') }))
    : { build: b, v: { verdict: 'skipped', blockers: [] }, blocking: [] },
  async (r, issue) => {
    if (/^\d+$/.test(String(issue.id)))
      await agent(commentPrompt(issue, r), { label:`note:${lbl(issue)}`, phase:'Build', model: MODELS.note }).catch(() => null)
    return r
  },
)

// ── 確定性閘門:build 完成 ∧(未開驗證 或 無 critical/high blocker)──
const eligible = todo.map((issue, i) => ({ issue, r: built[i] }))
  .filter(x => x.r && (!CONFIG.adversarial || (x.r.v && x.r.blocking.length === 0)))
const okIds = new Set(eligible.map(e => e.issue.id))
const blocked = todo.filter(i => !okIds.has(i.id)).map(i => i.id)
log(`${eligible.length}/${todo.length} 過閘門${CONFIG.adversarial ? '(含對抗驗證,只擋 critical/high)' : ''}` +
    (blocked.length ? `;未過:${blocked.join(', ')}` : ''))

if (!eligible.length) return { planned: todo.length, merged: 0, blocked, note: '沒有 issue 過閘門' }
if (!CONFIG.autoMerge)
  return { planned: todo.length, merged: 0, eligible: eligible.map(e => e.issue), blocked,
           note: `分支已備妥(從 ${CONFIG.baseBranch} 開),等你手動 merge / 開 PR,或傳 {autoMerge:true} 自動合(需使用者具名授權)` }

// ── ③ MERGE(跑一次:批次合併綠分支 + 收尾關閉 GitHub issue)──
phase('Merge')
const merge = await agent(mergePrompt(eligible.map(e => e.issue)), { label: 'merge', phase: 'Merge', model: MODELS.merge })
return { planned: todo.length, merged: eligible.length, blocked, merge }
