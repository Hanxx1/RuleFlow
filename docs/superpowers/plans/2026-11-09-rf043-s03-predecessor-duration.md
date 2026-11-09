# RF-043 S03 前置耗时不足最小修复 Implementation Plan

> **状态：2026-11-09 用户随后授权实施；局部修复及42项相关回归已完成，保留本地未提交。** 原方案与前一阶段失败证据如下；最新实施记录见文末。

**Goal:** 选集外未完成前置任务的已有安排不足其要求耗时时，预览阻止后置建议，与提交校验一致。

**Architecture:** 在现有 owner 隔离查询中取得前置耗时，通过内部参数传入 preview_schedule，使用现成 existing_minutes 判定足量后才采纳 existing_task_ends。保持提交时的实时校验与草案事务不变。

**Tech Stack:** Python、FastAPI、SQLite、pytest；无新增依赖。

**Spec:** [RF-043 矩阵 S03/S04](../../development/records/D_RF043_cases.md)、[公共决策表](../../development/records/D_public_interface_questions.md)。基线 main `4144bdb`，2026-11-09。

## 实施前：测试与定位交付证据（历史）

新增 `server/tests/test_schedule_predecessor_duration.py`，没有修改生产逻辑。

- 两个真实 HTTP 入口 `/api/v1/schedule/preview` 和 `/api/v1/schedule/drafts`，分别输入前置需90分钟、已安排30或89分钟，只选后置任务。
- 预期：正式日程不变，suggestions为空，后置进入 unscheduled，reason为现有 blocked_by_predecessor。
- 未标记时运行结果：4 failed、2 passed、5 warnings，退出1。四项失败均在不应生成后置建议的断言，不是准备数据或环境错误。
- 两项保护测试通过服务函数种入与旧预览结构一致的不合法草案，使用真实 owner 快照，再经 HTTP commit。确认409且错误为前置耗时不足，已有日程完整不变、草案pending、committed_at为空。此种入仅在测试隔离数据库，确保修复预览后仍能测旧草案的写入防线。
- 最终四项预览目标使用 strict xfail，只捕获专用 PartialPredecessorPreviewError；准备失败、HTTP异常或其他断言不会被吞掉。xfail不是通过或修复；XPASS严格失败提醒修复后移除标记。
- 与既有24项定向排程测试合跑：26 passed、4 xfailed、5 warnings，退出0。原有S04已覆盖完全缺失和完整90分钟可预览/提交两个对照。未跑全量、UI、Android或APK构建。

## 根因与调用链

1. `server/app/api/planning.py::schedule_preview`（基线209–218行）读取当前owner的任务关系、正式安排和所有任务status；只有选中任务携带duration_minutes。选集外前置任务只传status，没有耗时。
2. `server/app/services/schedule.py::preview_schedule`（176–181行）已累计每个task_id的existing_minutes和最晚结束时间。
3. 同函数（207–220行）对外部前置只要存在existing_task_ends就放行，用结束时间推进earliest，没有比对existing_minutes与前置耗时。输入也不足以完成这一判断。
4. `/schedule/drafts` 调用同一schedule_preview，因此直接预览与持久化草案共享缺陷。
5. `schedule_draft_commit → services/schedule_drafts.py::commit_draft → api/planning.py::validate_schedule_write`（77–82行）重新查询同owner前置的status、duration_minutes和所有安排，累计真实分钟；不足则409，或最晚结束晚于后置开始则409。因此预览能给建议而提交拒绝。

差异为「未传外部前置耗时＋预览分支漏判」，不是提交保护错误，也不是缺少已安排分钟统计。

## Global Constraints

- 用户随后明确授权按本方案实施S03局部修复，禁止提交/推送。该授权不替代其他公共契约的团队签认。
- 只改内部接口，不新增数据库迁移、HTTP字段、错误码或依赖。正式安排不能被预览修改。
- owner_id过滤必须保留，不能查询或利用其他owner的任务/安排。
- 保留done/skipped当前分支，不借本修复决定Q03；未知耗时仍沿提交端现有30分钟回退，不借此签认Q06。
- S05/S07、拆分策略、评分、独立Task、UI均不纳入本切片。

## 最小实现步骤（已执行）

### Task 1：补齐预览的外部前置耗时校验

**Files:** 修改 `server/app/api/planning.py`、`server/app/services/schedule.py`；测试 `server/tests/test_schedule_predecessor_duration.py`。不修改 `schedule_drafts.py`。

**内部接口建议：** 在 `preview_schedule` 现有preferences参数之后增加仅关键字参数 `all_task_durations: dict[str, int | None] | None = None`。现有纯函数调用保持位置参数兼容。缺少某个外部前置元数据时保守阻断，不能把缺失任务当成耗时30分钟；存在任务但duration为None时才沿用当前回退。

- [x] 再次确认工作区和协作文件占用；执行下方 `--runxfail` 命令，必须在四个已知断言失败，两项提交保护通过。
- [x] 在schedule_preview现有owner限定任务查询中增加duration_minutes列，构建statuses和durations两张映射，通过关键字传入算法。不能把外部前置加入选中tasks，避免静默扩大排程范围。
- [x] 在preview_schedule外部前置分支，要求其元数据存在、已有安排存在且existing_minutes达到`duration_minutes or DEFAULT_SLOT_MINUTES`，满足后才使用existing_task_ends；否则加入blockers，复用blocked_by_predecessor。detail可明确“前置任务未完成或已有安排时长不足”，不增加未评审的结构化字段。
- [x] 判断按真实累计分钟，与提交端一致，不向上取整已安排时长；也不要把前置要求按30分钟槽向上取整（例如要求31分钟、已有31分钟应与提交端一致）。选中任务的分配粒度不在本修复范围。
- [x] 保留提交校验、事务、草案快照和最晚结束时刻约束。不要通过取消提交校验来消除差异。
- [x] 修复后移除四项strict xfail及专用异常，恢复普通断言。两项旧草案保护测试应保持通过。

### Task 2：验证边界并更新记录

本轮补充以下边界测试：

- [x] 多个已有片段累计60/90分钟阻断、累计90/90分钟放行；使用纯算法合成片段，检查最晚结束时刻。HTTP路径由S04与31分钟用例验证。
- [x] 已完成前置即使不足量仍沿原逻辑放行；skipped不改变语义，仅验证兼容。
- [x] 31分钟要求、31分钟已有安排的非槽整数边界，与提交一致；保持89/90阻断。
- [x] 外部前置元数据缺失时保守阻断；同owner其他任务的占用不能贡献该前置的分钟。
- [x] owner隔离：另一账户的任务与安排不能补足当前前置，也不能进入结果；确认实际查询仍有owner过滤。
- [x] 跑新增测试及全部相关排程测试，S04缺失/足量和既有拆分/依赖/原子回滚均通过；再核验API契约无变化。
- [x] 更新D矩阵和工作记录，说明S03修复范围及未测边界。提交、推送或PR需另有用户授权，不在本计划自动执行。

## 可复现命令

仓库根目录，复用已有 `.runtime/review-venv`，无在线模型，内存数据库和临时上传目录。

历史缺陷复现命令（修复后该文件18项全部通过，无xfail）：

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_predecessor_duration.py --runxfail -q -p no:cacheprovider --tb=short
```

定向回归（修复后42项全部通过，无xfail）：

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_predecessor_duration.py server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings
```

本轮没有可交付APK；S03已完成局部修复与定向回归。S05/S07与其他公共契约待确认事项仍开放。


## 实施记录（2026-11-09）

- 两个生产文件变更：owner限定的任务查询增加duration_minutes并传入内部参数；外部前置必须有耗时元数据且累计分钟足量才使用其结束时刻。保留全部提交校验；不自动将前置加入选集。
- 新测试文件共18项：原6项移除strict xfail；补12项覆盖多片段累计、done/skipped、缺元数据、None耗时的29/30分钟边界、无关任务时长、31分钟HTTP预览/提交、异账户访问与占用隔离。
- RED：18项运行15 failed、3 passed；包括原4项真实缺陷、owner场景的错误放行，以及新内部关键字尚未实现导致的10项TypeError。之后首次实现因文本替换未命中漏定义durations，相关回归19失败23通过（NameError）；补齐映射后42 passed、5 warnings、退出0。
- API契约核验通过，OpenAPI指纹仍为`aa40e470df16fa9b2143aa452c92dab9debaa18467e3b9a7694cbeb95df838ed`。没有重新批准或更新API基线。
- Ruling: 在当前有上轮未提交测试/文档的工作区实施，不迁移或提交已有材料；用户要求本地修复且禁止提交推送。代价是交付需按文件区分前后两阶段改动。
- Ruling: 多片段累计在纯算法层验证，HTTP实际数据流以S04足量及31分钟端到端用例覆盖；无需绕过创建接口或扩大生产变更。限制是未新增多片段HTTP端到端用例。
- 未运行全量后端、移动端/真机或APK构建；本轮没有修改UI状态。S05/S07不在授权修复范围。

## 独立审查结论

只读独立审查未发现Critical/Important问题，未再运行测试。确认内部接口兼容、owner过滤、真实分钟阈值、缺元数据保守阻断及提交防线保持。

- Ruling: 选中任务的30分钟槽处理仍属既有行为，不纳入外部前置修复；代价是本次不解决其他选集场景的舍入差异。
- Ruling: skipped和未知耗时确认流程维持现状，Q03/Q06仍待公共决策；本次测试仅证明兼容，不代表产品语义已签认。
- 边界：多片段、done/skipped、None回退由纯算法测试覆盖，没有新增各自HTTP提交路径；31分钟、S04足量、旧草案拒绝有HTTP验证。全量、UI、Android/APK未验证。
- 最终差异检查通过，文档本地链接检查通过（158处）。用户要求不提交/推送，全部文件保留本地；没有临时分支合并或发布动作。
