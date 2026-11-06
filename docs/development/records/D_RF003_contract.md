# 有绪 CampusWeave｜RF-003 Task 与排程契约草案

日期：2026-11-05；负责人：D；依据：源码 `ac9e07c`、首批任务表、开发指导第 4 节。
状态：D 侧走读与提案已整理，待 C 共拟、A/B 评审。本文不是已批准接口，不实施迁移。公共未决项统一见 [确认清单](D_public_interface_questions.md)。

## 1. Task → 草案 → 正式日程走读

| 环节 | 实际入口与行为 | 消费者 / 注意事项 |
|---|---|---|
| 通知确认生成 Task | `server/app/services/review.py::confirm_review/compiled_task_id`；由确认候选生成，任务 ID 保持已有 ID 或确定性 UUID | C 的通知办理；不得绕过确认 |
| 手动添加事项内 Task | `main.py::create_task`，POST `/api/v1/cases/{case_id}/tasks`；校验 owner、EvidenceRef、Review，事务中复核门禁，初始 todo | 尚非独立 Task；deadline/耗时补用户输入证据 |
| 状态更新 | `PlanView.vue::changeStatus` → `features/cases/store.ts::setTask` → PATCH `/api/v1/tasks/{task_id}` → `main.py::patch_task` | 当前仅 status；todo/in_progress/done/skipped；没有日程完成或提醒联动。无登录 store 走 Demo 本机状态，不作为账户实测 |
| 计划读取 | `PlanView.vue::selectCase` → store.loadPlan → GET `/api/v1/cases/{case_id}/plan` | ordered_tasks / edges / 进度供清单和排程页使用 |
| 排程参数 | PUT `/api/v1/tasks/{task_id}/planning`，`api/planning.py::update_task_planning` | duration、splittable、min/max chunk、importance/preference；已有安排则 409，用户填写生成 Evidence |
| 请求草案 | `PlanSchedule.vue::makePreview` 读取 owner 的 Workspace，expandCourses；确认发送占用后 POST `/api/v1/schedule/drafts` | 当前发送 case_id 而非选定 task_ids；窗口 14 天、Asia/Shanghai；只传占用与引用，不传课程名 |
| 预览与持久化 | `planning.py::schedule_draft` 先取 snapshot → `schedule_preview` → `schedule.py::preview_schedule` → 事务内再比 snapshot → `schedule_drafts.py::create_draft` | 预览 API 自身不落日程；draft 保存不可变结果、state_hash、pending，不表示正式安排 |
| 确认 | `PlanSchedule.vue::confirmDraft` 再读 Workspace revision、用户确认 → POST `/api/v1/schedule/drafts/{id}/commit` | `consent:true` 与 calendar_revision；没有草案编辑请求 |
| 提交 | `commit_draft` 校验 owner、consent、calendar revision/冲突、snapshot，再逐条 `validate_schedule_write`，事务写 schedule_items，标 committed | 同一已提交草案重复确认幂等；重复确认仍先检查 consent/calendar。失败回滚；这不等于任意多次新建日程幂等 |

Review 精确边界：`require_confirmed` 对存在未确认 review，或没有 review 的历史导入 Case 且非 demo 的情况拒绝；不能概括为所有手动 Case 必须有 review 记录。

## 2. 数据、引用与授权

| 实体 | 当前代码事实 | RF-003 提案（待审） |
|---|---|---|
| Task | bootstrap 中 case_id NOT NULL；evidence_ids_json；四种状态；PatchTask 只有 status | 沿用同一 tasks，支持手动来源和通知确认来源；独立任务允许 case_id 空；字段名与迁移编号未定 |
| Evidence | case_id NOT NULL；创建 Task 要求同 owner/Case 的有效引用 | 与 C 的 RF-002 共用唯一规则；独立用户输入仍生成可追溯依据，不借假 Case 绕过约束 |
| TaskEdge | 现有新增路由限定同 Case，拒绝自依赖/环，并保护已有后置安排 | 空 Case 和跨 Case 依赖必须明确范围及 owner 校验，不只修改 schema |
| ScheduleItem | busy/course/task；case_id、task_id 可空，但 task 类型必有关联；没有独立完成状态 | “何时做”，与“做什么”分离；独立事件类型/状态待定，不复制 Task |
| Course | 本机 Workspace 展开 calendar_blocks，携带 revision 和本机证据引用 | 继续用途授权后只发送必要占用；不默认全量上传或建第二套课表库 |
| Draft | pending/committed；owner 范围指纹包含 tasks、edges、items、reviews、planning、locks | 编辑/固定/重算生成新不可变版本；新版本及旧草案失效方案待 RF-045，暂不新增 URL |
| Lock / Reminder | 锁绑定正式 item_id；尚无本地提醒完整实现 | 草案固定与正式锁分离；提醒绑定 schedule_id/revision，RF-007 验证后再定 |

指纹以 owner 全范围计算，其他事项变动也可能使草案 stale。calendar_revision 由客户端提交并与草案比较；服务器不会自动知道设备上的最新课表版本。旧 suggestions 没有独立 evidence_ids 字段，不能宣传所有排程解释已直接附完整 EvidenceRef；后续应沿 task_id 可回查且在响应/UI 明确依据，见 Q02。

## 3. 操作前后状态矩阵

以下“建议结果”不是现有功能已实现的声明。

| 操作与输入示例 | 当前行为 | 建议结果 / 决策 |
|---|---|---|
| 用户新建独立 T，无 Case | 无独立创建入口，表结构不支持 | T 保存用户来源依据，case_id 空；通知来源仍受 Review 门禁（Q01/Q02） |
| T:todo → in_progress → done | PATCH 更新 Task；不联动日程/提醒 | 取消未来提醒，保留历史安排；不把每片日程伪造为已执行（Q03） |
| 前置 A:todo → skipped，B 依赖 A | 当前预览/提交均放行 | 保留 skipped 与 done 区别；是否继续阻断或显式豁免待确认（Q03） |
| T 被分为 S1、S2，完成 S1 | 无日程完成字段/API | 只完成 S1；不自动完成 T/S2，是否提示完成整个清单待确认（Q04） |
| 删除 S1，T 存在 | 删除日程不删除 Task；锁或已有后置安排可阻止删除 | 保留限制及 T；同时撤销该提醒（Q04/Q09） |
| 删除 T 或材料 | 当前 Task 无独立删除契约；材料/原件关联需消费者盘点 | 展示影响并确认，不级联删除原件；具体解绑/保留行为待 C/B（Q05） |
| T 已安排 60 分钟，改预计耗时 90 | planning 更新返回 409 | 首版保留显式移除后修改；更友好变更预览另行定，不静默丢日程（Q06） |
| 修改执行时间 | 校验截止/依赖/冲突/锁，不改 Task 截止 | 保持；改时后旧提醒撤销，新版本建立（Q09） |
| 生成草案后取消 | 不 commit 则不写正式日程；未见取消接口 | 取消建议不改清单/日程；pending 草案留存策略另定（Q08） |
| 课表 revision 2 → 3 后提交旧草案 | 当前客户端检查 + 服务端版本比较拒绝 | 重算新草案，不覆盖新课表；须明确可信版本边界（Q08） |
| task_ids=[] 或不传 | 当前都选择范围内全部未完成任务 | 新选择入口“无选择”不应变全选；兼容旧页面需要明确区分（Q07） |

## 4. 当前协议样例

合成 ID 为占位，不是实际资源；实际创建过程见边界实验脚本。外层成功响应为 data/request_id，错误 detail 可能是字符串或 code/message，不能要求消费者只解析统一错误对象。

```json
{"task_ids":["T1"],"window_start":"2099-01-01T08:00:00+08:00","window_end":"2099-01-01T12:00:00+08:00","timezone":"Asia/Shanghai","calendar_blocks":[],"calendar_revision":2}
```

POST drafts 成功 data 含 draft_id、state=pending、suggestions、unscheduled、timezone/window/preferences；一个 T 可有多片 suggestions，不能按数组长度当任务数。确认请求 `{ "consent": true, "calendar_revision": 2 }`，首次成功含 saved_count；重复提交 idempotent=true。不确认 422；其他 owner 的草案 404；任务/占用变化 409 DRAFT_STALE；课表版本不同 409 CALENDAR_STALE；占用/截止/依赖失败目前可能是字符串 409。

UNKNOWN：不能降为 FALSE。当前 PlanSchedule 的本机 relevance=FALSE 阻止自动排程，但 UNKNOWN 不等于“资格通过”；需与 C 明确缺字段提示和办理确认边界，不能让 D 再做一套资格判定。

## 5. 兼容影响与后续边界

- 038/039 前盘点 bootstrap/migrations、TaskIn/PatchTask、create/patch_task、Review、Evidence 校验、task_dtos/DAG、按 Case 查询、统计/导出、Vault 引用、owner/退出生命周期、前端 product 类型。此为影响清单，尚未逐个完成迁移设计；排序 `_sort_tasks` 的 tie-break 使用 case_id，空值与字符串混排也需回归。
- 旧库回归计划：保留旧 Case/Task/Evidence ID；历史通知未确认仍阻断；旧 task_ids 缺省消费者行为兼容；跨 owner 查询/更新/草案提交拒绝；统计不把独立任务丢失；导出可回查依据；迁移失败回滚。未执行迁移测试。
- C 的 RF-040 消费同一 Task，C 负责清单页面；D 不另建清单系统。B 的 RF-012 需明确课程 revision/退出与授权快照。
- 顺序：RF-001 样例与 RF-002/003 共识 → 038/039（与 C 的 015 协调迁移）；003 → 041/043；043 → 044 → 045 → 046/047；007 选型 + 041 状态 → 048。042 需真实课表样本及 012。
- 下一轮最小修复候选为 RF-043 的前置耗时、过去时间和时区一致性；不顺带开发多方案评分、草案编辑或 Android 插件。

## 6. 验证与限制

14 项现有定向测试通过，3 项边界实验复现现有缺口，详见 [RF-043 样例](D_RF043_cases.md) 和 [D 工作记录](D_scheduling.md)。本契约未获 C/A/B 签认，未执行数据库迁移、完整浏览器或真机验收，不标 RF-003 整卡完成。
