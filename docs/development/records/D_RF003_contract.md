# 有绪 CampusWeave｜RF-003 Task 与排程契约草案

日期：2026-11-05；负责人：D；依据：源码 `ac9e07c`、首批任务表、开发指导第 4 节。
状态（2026-11-09更新）：D侧提案已整理；C已在RF-002第9节接受Q01/Q02核心语义，A/B协调确认及B消费核对仍待补齐；课程增量尚待共同评审。本文不是已批准接口，不实施迁移。公共未决项统一见 [确认清单](D_public_interface_questions.md)。

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

## 6. 初版验证与限制（历史，当前状态见唯一决策表）

14 项现有定向测试通过，3 项边界实验复现现有缺口，详见 [RF-043 样例](D_RF043_cases.md) 和 [D 工作记录](D_scheduling.md)。本契约未获 C/A/B 签认，未执行数据库迁移、完整浏览器或真机验收，不标 RF-003 整卡完成。

## 7. 2026-11-08 C/D 契约对齐提案：Q01 / Q02

状态（2026-11-09更新）：C已在RF-002第9节接受本节Q01/Q02核心语义，待A/B协调确认及B消费核对；详细状态只见唯一决策表。依据 main `4f9b266` 的 [C RF-002 第3–7节](C_RF002_contract.md)、`server/app/main.py::validate_evidence_refs/create_task/patch_task/task_dtos`、`server/app/schemas.py::TaskIn/PatchTask` 及本契约。唯一签认入口仍为 [公共决策表](D_public_interface_questions.md)，本节不另建审批状态。

### 7.1 已对齐方向和剩余差异

| 主题 | C 已提出的意见 | D 本轮具体建议（待共同确认） |
|---|---|---|
| Task 身份 | 唯一 Task；通知来自确认 Review；手动任务不伪装通知 | 保留原 tasks 与 ID，新增独立创建能力；来源与 Case 归属分开表达，不能从 case_id 是否为空推断来源 |
| 依赖范围 | 首轮不默认跨 Case | 保留同一非空 Case 内依赖；允许同 owner 的独立任务之间依赖；首轮拒绝跨 Case 及独立↔Case 混合依赖。多任务一起排程不等于允许跨范围建边 |
| Evidence 身份 | 同一模型，独立用户依据可空 Case；不能只放松 NOT NULL | 增加可验证的作用域绑定：case 作用域或 task 作用域。独立用户依据绑定一个 task_id，不是 owner 下任意任务都能复用 |
| 排程引用 | 至少 task_id＋受控解析路径/缺失状态；显式 refs 待定 | 新响应增量提供 evidence_ids 和 evidence_state，保留 task_id、suggestions；引用详情经受控任务证据接口解析，不能把客户端任意 URL 当解析入口 |
| UNKNOWN | C 提供资格及缺字段信息，D不重判 | 透传 C 的字段；区分用户安排依据、官方事实和资格判断。用户确认日程不会把 UNKNOWN 改为 TRUE |

### 7.2 Q01 推荐契约

以下字段、URL、错误码均为提议，未实现；既有 URL 保持可用。

- Task 来源建议 `origin=review_confirmed | user_input | legacy_unknown`，由服务端创建路径确定；客户端不能通过提交 origin 绕过 Review。Case 内手动任务仍是 user_input，独立任务首版只允许 user_input。旧记录无法可靠溯源时用 legacy_unknown，不补造确认历史。
- `case_id` 可空，`owner_id` 从会话取得。`case_id=null` 不等于免检：仍须核对任务 owner、task 作用域证据、依赖、截止与占用；非空 Case 继续走当前 require_confirmed 语义，不扩大成所有手动 Case 必须存在 Review。
- 建议新增 `POST /api/v1/tasks` 专供独立任务：title、可选 deadline/duration_minutes、consent、operation_id；不接受任意外部 evidence_ids 或 Case 绑定。服务端在同一事务创建 Task、用户输入 Evidence 和引用，初始 todo，失败全部回滚。用户明确填写的标题/截止/估时是“用户输入依据”，不能当官方通知证据；缺失的截止/估时不补造。
- 现有 `POST /cases/{case_id}/tasks` 保持证据与 Review 门禁。现有 `PATCH /tasks/{id}` 继续只承担 status；建议独立内容编辑使用 `PATCH /tasks/{id}/content`，携带 expected_revision 和 consent，仅允许独立 user_input Task；更新时新增不可变依据版本，保留历史引用。已有安排时对截止/耗时等约束变更先返回409，后续影响预览归 Q05/Q06，不静默移动日程。
- 建议读取 `GET /tasks/{id}` 返回同一 Task DTO；独立依赖建议 `POST /task-edges`，只接受同 owner、两端 case_id 都为空的任务和明确用户输入依据。既有 Case edges 入口继续同 Case 限制。两入口复用自依赖、环、已有后置安排保护，不能仅前端禁用。
- 独立 Task 首轮不提供“改 case_id”操作；绑定/迁移到 Case 将涉及 Evidence 作用域、Review、依赖和日程，另行评审。跨 Case/混合依赖建议409且无写入，越权保持404。

### 7.3 Q02 推荐契约

**作用域规则（待审）**：沿用同一 Evidence 身份与存储模型，逻辑字段建议 scope_kind、scope_task_id；DDL是否用绑定表由迁移设计确定，不在此处指定迁移编号。

| 引用者 | 可引用 Evidence | 必须拒绝 |
|---|---|---|
| Case 内 Task/材料/规则 | 同 owner、同 case_id 的 case 作用域 Evidence | 其他 Case、其他 owner、task作用域引用 |
| 独立 Task | 同 owner、case_id为空、scope_task_id恰为当前Task的user_input依据 | 其他独立Task依据、任意Case依据、无有效作用域的孤立引用 |
| 未确认候选 | RF-002 的 source_ref，包含真实来源/行/版本 | 把 source_ref ID 直接作为正式 EvidenceRef 或创建可执行Task |
| 排程建议 | 沿当前Task获得有效引用，保留其scope与来源 | 仅凭 evidence_id 存在或 owner 相同即放行；缺引用时显示“待核对”而伪造依据 |

- scope_kind=case 时 case_id 非空且 scope_task_id 为空；scope_kind=task 时 case_id 为空且 scope_task_id 非空。同 owner 校验之外还要检查这组互斥约束。独立 Task 与依据绑定在一个事务内完成；环形外键/插入顺序须在迁移方案中验证，不能仅放宽列约束。
- 候选→Case确认沿 C 的 source_ref→每Case Evidence 映射；随后仍须行动确认才生成通知 Task。共享 Document 行可被多个 Case 各自产生 Evidence，不能跨 Case 直接复用 Evidence ID。手动创建独立 Task 不消费未确认候选来绕过这两道门禁。
- 建议受控读取 `GET /tasks/{id}/evidence`，先验证 Task owner，再逐项验证引用作用域；不接受客户端 owner_id。响应含有效依据和缺失/待核对状态；跨 owner 请求404，内部不合法引用不泄露他人摘录。
- 新排程响应建议增量增加 evidence_ids、evidence_state（valid/needs_review）及缺失提示；旧响应缺字段时消费者按未知处理，通过任务接口回查，不能自动解释为valid。保留旧 suggestions 和外层 data/request_id；该增量须与 Q10 的 OpenAPI/客户端兼容评审合并。
- 独立 Task 无官方资格结论，不伪造 Case 的 relevance=TRUE。Case Task 继续消费 C 提供的 relevance、relevance_reason、missing_profile_fields、missing_case_fields；UI显示UNKNOWN及待补字段。资格与是否允许执行的业务门禁需按 C Review 判定，不能由 evidence_state=valid 推出资格通过。
- 用户依据在内容编辑时新增版本；历史草案不得静默换成新依据。变化纳入草案失效指纹或 revision 校验。独立 Evidence 首版不开放单独删除入口；删除Task/解绑仍依 Q05 的影响预览及消费者确认，不在Q02里擅定级联策略。任何路径不得级联删除Document/Vault原件。

### 7.4 兼容、实现顺序与待验用例

1. C/D先确认语义和字段，再由A/B协调 RF-015 与 RF-038/039 的公共迁移顺序。C负责候选映射；D负责独立Task/依据作用域与排程消费；C的RF-040消费同一DTO，不另造Task。
2. 旧Case/Task/Evidence ID、status、引用保持不变。已有非空Case证据可映射case作用域；不能从文本标题猜origin，无法可靠溯源标legacy_unknown。旧行缺有效引用不补假证据。旧库外键、owner组合约束、回滚和混排排序必须测。
3. 先扩展存储约束和共享校验，再接新入口与DTO，最后接D排程/C清单；既有Case路径、Offline Demo与旧status PATCH必须回归。内容变更版本和幂等字段的DDL由同一迁移批次协调。
4. 独立创建建议 owner+operation_id 幂等，同键同内容返回原回执，同键异内容409；重放先校验访问权限。编辑expected_revision过期409，失败不新增依据或修改正式安排。并发两请求同键应只有一组Task/Evidence；不能以顺序请求通过冒充并发验证。

| 待验场景 | 预期结果（均未执行，功能尚未实现） |
|---|---|
| 手动独立任务创建、重试 | 一个Task及绑定的用户依据；无假Case；同键重试不重复 |
| 第二步Evidence写入失败 | Task/依据/回执全部回滚，无孤立记录 |
| 同owner另一独立Task证据；其他Case证据 | 引用校验拒绝，不能仅owner相同即放行 |
| 其他owner读取Task/依据 | 404且不泄露摘录 |
| 未确认候选直接创建通知Task | 拒绝；确认映射及Review门禁仍生效 |
| 独立↔独立／Case内／跨Case／混合依赖 | 前两类在无环且约束满足时允许；后两类拒绝；无部分写入 |
| 旧客户端、历史数据、UNKNOWN | 旧入口可用，ID/status不变；缺引用待核对，UNKNOWN与缺字段原样保留 |
| 内容变更后提交旧草案 | 版本/指纹冲突拒绝；正式安排不变；不自动重排 |

**请求确认的最小决策包**：Q01确认来源分类、独立入口/编辑边界、依赖范围；Q02确认task作用域绑定、排程显式引用＋受控解析、UNKNOWN消费与删除保护。具体确认成员、日期、讨论链接只写回唯一公共决策表。未收到签认前，本节只能作为实现准备，不能标RF-003完成。


## 8. 2026-11-09 评审状态与 CM-001 接续

C最新`f34e70e`第9节接受第7节Q01/Q02的核心语义，包括独立依赖边界、task作用域Evidence、显式排程引用与UNKNOWN透传。第7.1节“显式refs待定”是早期C意见，已被最新接受意见替代；具体公共接口和迁移仍未获团队定稿。签认状态、余留输入及阻塞只维护在 [唯一公共决策表](D_public_interface_questions.md)。

CM-001的D部分也在同表维护：课程/学期与Task关联、规则/发生时段的唯一占用、截止变更影响、备份删除检查及混合输入执行结果，含6组未执行的合成样例。不新增第二套Task、Evidence或课程协议，不将C对Q01/Q02接受扩大成课程增量接受。本轮未实施接口或迁移。
