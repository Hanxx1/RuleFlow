# 知事 / RuleFlow Simulation Backend 实施计划

> 修订日期：2026-09-22
>
> 本轮目标：为比赛初赛提供“全功能可交互后端壳”，同时保持可逐步替换为真实后端的 API、Service、Repository 和 Provider 边界。
> 事实基线：`docs/archive/FEATURE_AUDIT.md`；前端现状：`docs/product/FRONTEND_CAPABILITY_MAP.md`。

## 1. 本轮边界

统一架构：

```text
Frontend
  -> 同一套 /api/v1/* API contract
  -> Service
  -> Repository / Provider abstraction
  -> DEMO_MODE=true  : Demo implementation + demo.db
  -> DEMO_MODE=false : Real implementation
```

必须遵守：

1. Demo 与 Real 共用 route、请求 DTO 和响应 DTO；不新增 `/api/v1/demo/*` 业务接口。
2. `DEMO_MODE=true` 时整个实例使用独立 `demo.db`，包括 Auth、Profile 和业务表；Demo 数据不得写入正式账户数据库。
3. `shared/demo` 只保存可提交的只读脱敏 seed；运行时 mutation 写入 `demo.db`。
4. Demo CRUD、任务状态、排程、ImportBatch、Vault 关联均真实持久化，重启或刷新后可恢复。
5. Demo/Real 差异只存在于 Repository/Provider 选择层；前端业务逻辑不得依赖 Demo 专属字段。
6. 可在统一 envelope 的可选 metadata 中返回 `backend_mode`，仅用于环境提示。
7. `DEMO_MODE=false` 时不得把 `shared/demo` 当作业务 fallback。未配置的真实 Provider 应明确返回 unavailable。
8. 不绑定 PostgreSQL、Redis、Vector DB、对象存储或第三方 Calendar。
9. 不大规模重构 `main.py`。抽象只覆盖本轮新增模块、必须复用的查询及未来明确需要替换的 Provider。
10. 现有 21 个后端测试必须持续通过。

现有只读 `/api/v1/demo/notices/assessment` 可暂时保留兼容，但新页面与新能力不得依赖它。

## 2. 数据隔离和运行模式

建议配置：

```env
DEMO_MODE=true
DATABASE_PATH=server/data/ruleflow.db
DEMO_DATABASE_PATH=server/data/demo.db
DEMO_UPLOAD_ROOT=server/data/demo_uploads
```

选择规则：

- `DEMO_MODE=false`：活动数据库为 `DATABASE_PATH`。
- `DEMO_MODE=true`：活动数据库为 `DEMO_DATABASE_PATH`。
- 两个路径解析后相同时，应用必须启动失败。
- `demo.db`、WAL/SHM 及 `demo_uploads` 不得提交 Git。
- 不采用在正式业务表中增加 `is_demo` 的混库存储方案。
- 所有私有记录继续按 `owner_id` 隔离。

统一响应 envelope 非破坏性扩展为：

```json
{
  "data": {},
  "request_id": "...",
  "meta": {"backend_mode": "demo"}
}
```

现有前端读取 `data` 的代码保持可用。`meta.backend_mode` 只能用于环境提示，不得决定 DTO 解析或业务分支。

### 2.1 Phase 0 合同约定

- 日期使用 `YYYY-MM-DD`；具体时间使用带时区的 RFC 3339/ISO-8601 字符串，禁止写入无时区 timestamp。默认业务时区为 `Asia/Shanghai`。
- Case 状态为 `draft/review/in_progress/completed/archived`；`deleted` 只作为内部 tombstone，不进入普通列表。
- Task 状态继续使用 `todo/in_progress/done/skipped`。
- ImportBatch 状态为 `queued/processing/completed/partial_failure/failed`。
- Schedule kind 为 `task/busy/course`，source 为 `manual/fixture/generated/imported`。
- 列表 cursor 为服务端生成的不透明字符串；客户端不得解析或拼接。`limit` 默认 20，范围 1–100。
- 成功响应使用 `{data,request_id,meta?}`。应用错误保留字符串 `detail` 以兼容当前前端，并可增加稳定的 `error.code`；客户端不得根据中文 message 做业务判断。
- 新接口参数错误使用 422，未认证使用 401，已认证但无权访问的私有资源统一表现为 404，状态冲突使用 409，Provider 未配置使用 503。
- Case/Plan 进度只按 `done / total` 计算并四舍五入为 0–100 整数；`skipped` 不计完成，无任务时为 0。

## 3. 当前已有能力：保留，不重写

| 能力 | 当前接口/实现 | 本轮处理 |
|---|---|---|
| Auth | 注册、验证、登录、刷新、重置、sessions、logout | 保留；补 `token_type` 和后续单设备撤销 |
| Profile | `GET/PUT /api/v1/profile` | 保留；增加 completeness |
| Case | 创建、列表、详情、resources、evaluate | 兼容扩展查询、PATCH 和聚合字段 |
| Evidence / Rule | SQLite + EvidenceRef + Rule AST | 保留；加强 owner/Case 一致性校验 |
| Task DAG / Plan | Task、Edge、拓扑排序 | 保留；扩展 DTO 和聚合结果 |
| Task status | `PATCH /api/v1/tasks/{id}` | 保留；进度动态计算 |
| Text/URL/File import | `/api/v1/imports/*` | 保留；新增 ImportBatch 作为新流程，不提前删除旧接口 |
| 解析与分析 | parser、本地规则、可选 LLM | Real provider 复用；Demo provider 可使用 fixture/规则 |
| Privacy | 身份证、手机号、银行卡正则 | 扩展为结构化 API，不保存原文 |
| TXT/ICS export | 现有导出 | 本轮不重写 |

当前修复项：

- access/refresh session 缺少类型隔离；
- Edge 未验证两个 Task 均属于 URL 中的 Case；
- Task/Material 写入时未验证 EvidenceRef 同 owner、同 Case；
- DAG 递归函数存在可变默认参数；
- 新 schema 需要最小版本化 migration。

## 4. 最小代码结构

```text
server/app/
  settings.py
  migrations.py
  services/                 # 仅新增能力和必要聚合
  repositories/
    protocols.py            # 仅明确替换边界
    sqlite.py
  providers/
    scheduling.py
    knowledge.py
    vault_content.py
    analysis.py
  demo/
    bootstrap.py
    reset.py
```

不要求把现有 Auth、Case、Task、旧 Import 的全部路由和 SQL 一次性迁出 `main.py`。

## 5. Demo bootstrap、fixture version 与 reset

### 5.1 Bootstrap

- `shared/demo/fixture_version.json` 保存当前 fixture 版本。
- `demo_seed_state(owner_id, fixture_version, seeded_at)` 记录每个 Demo owner 的 seed 状态。
- Demo owner 登录后，若未 seed，则把脱敏 Case/Evidence/Rule/Material/Task/Profile 等初始数据克隆到 `demo.db`。
- Fixture 业务键通过 UUIDv5 等方式生成 owner 级 deterministic UUID，确保测试与视频脚本稳定，同时避免不同 owner 主键冲突。
- 相同 fixture version 重复 bootstrap 不得重复插入。
- fixture version 变化时允许对该 Demo workspace 执行 reset 后重新 seed，不得影响正式数据库。

### 5.2 Reset

Reset 不是正式业务 API。首选 CLI：

```powershell
cd server
python -m app.demo.reset --user demo@example.com
```

仅当 `DEMO_MODE=true` 时可运行。Reset 必须：

1. 删除目标 owner 的 Case/Task/Schedule/Vault/Import 等业务 mutation；
2. 删除 `DEMO_UPLOAD_ROOT/{owner_id}` 下的 Demo 上传文件；
3. 清除目标 owner 的 seed state；
4. 按当前 fixture version 重新 seed；
5. 保留账户本身，且重复执行结果一致；
6. 不允许通过路径逃逸删除 upload root 之外的内容。

后续新增 Schedule/Vault/ImportBatch 表时，必须同时登记到 reset 清理清单和 reset 测试中。

## 6. API 与实现计划

### 6.1 Case

```http
GET /api/v1/cases?q=&status=&category=&deadline_from=&deadline_to=&sort=&limit=&cursor=
PATCH /api/v1/cases/{id}
```

列表 `data` 继续保持数组，避免破坏现有前端；分页信息放在 `meta.pagination`。列表项增加 `task_count/done_task_count/progress`。`done_task_count` 仅统计 `done`；`skipped` 不计入完成进度，但可解除 DAG 后继依赖；无任务时进度为 0。

PATCH 支持 `title/category/status/deadline`。字段 provenance 不伪造 Evidence：

```json
{
  "deadline": "2026-10-01T23:59:59+08:00",
  "deadline_source": "user_input",
  "deadline_evidence_ids": []
}
```

`source` 至少允许：`document/knowledge/user_input/generated`。只有来自文档或知识来源的值才关联真实 EvidenceRef。相同原则适用于未来的 location/person/priority。

### 6.2 Task / Plan

Task DTO 增加 `duration_minutes/deadline/materials/files/is_actionable`。Plan 保留 `ordered_tasks` 和 `edges`，增加：

```text
overall_progress
current_tasks       # 当前可执行 Task DTO 数组
completed_tasks     # 数量
pending_tasks       # 数量
```

`is_actionable`：自身为 `todo/in_progress`，且所有前置任务均为 `done/skipped`。

### 6.3 Schedule

```http
GET    /api/v1/schedule
POST   /api/v1/schedule/items
PATCH  /api/v1/schedule/items/{id}
DELETE /api/v1/schedule/items/{id}
POST   /api/v1/schedule/preview
```

Demo busy blocks 从 fixture 初始化到 `demo.db`。Preview 按 deadline、DAG 顺序和稳定 task id 排序；duration 向上取整到 30 分钟；排除 busy/course/已有 task item；不跨 deadline；相同输入与相同数据库状态返回相同建议。Preview 不落库，确认后通过 POST item 保存。未来只替换 Availability/Calendar Provider，不改变 API。

### 6.4 Knowledge Evidence

```http
GET /api/v1/cases/{case_id}/knowledge-evidence
```

```json
{
  "status": "available",
  "items": [{
    "title": "...",
    "publisher": "...",
    "effective_date": "...",
    "matched_section": "...",
    "quote": "...",
    "url": "...",
    "confidence": null,
    "match_type": "fixture_keyword",
    "match_score": 0.8,
    "evidence_ids": [],
    "reference": {"document_id": "...", "version": "...", "locator": "..."}
  }]
}
```

- `quote` 必须是 `shared/demo/knowledge` 源文档的真实子串。
- 当前没有概率模型时 `confidence` 必须为 `null`。
- deterministic 匹配程度使用独立的 `match_type/match_score`。
- Real mode 未配置知识 Provider 时返回 unavailable，不得读取 Demo fixture。

### 6.5 Vault

```http
GET    /api/v1/vault/items
POST   /api/v1/vault/items
GET    /api/v1/vault/items/{id}
PATCH  /api/v1/vault/items/{id}
DELETE /api/v1/vault/items/{id}
GET    /api/v1/vault/items/{id}/content
```

预置材料由 `shared/demo/files` 提供。用户在 Demo 运行中上传的真实文件必须由 Demo local content provider 保存到 `server/data/demo_uploads/{owner_id}/{file_id}`。

要求：保存文件和 metadata；查看时返回原上传内容，不映射成其他 fixture；删除 metadata、关联及内容文件；owner 隔离和路径逃逸防护；API DTO 不暴露本地路径；未来通过替换 `VaultContentProvider` 接入对象存储。

### 6.6 Profile completeness

`GET /api/v1/profile/completeness` 首版对 `student_type/enrollment_year/college/major` 各计 25 分，返回 score、completed_fields、missing_fields，从当前 owner Profile 动态计算。

### 6.7 Privacy

`POST /api/v1/privacy/analyze` 返回 findings、redacted_text、unsupported_types。支持身份证、手机号、银行卡号；避免规则重叠匹配；原文和 finding 不写数据库或日志。`start/end` 统一使用 Unicode code point 索引。

### 6.8 Dashboard

`GET /api/v1/dashboard` 返回 total_cases、in_progress_cases、due_soon_cases、completed_cases、recent_cases、today_tasks。所有数字从当前活动数据库实时聚合，禁止写死。

### 6.9 Account / Device

```http
DELETE /api/v1/auth/sessions/{id}
GET    /api/v1/account/settings
PATCH  /api/v1/account/settings
```

`sessions.token_type` 区分 access/refresh：业务 API 只接受 access，refresh API 只接受 refresh，设备列表只返回 refresh session，同一登录的 access/refresh 共享 family。账户设置首版只支持 display_name、locale、timezone；不实现生产 SMTP、修改邮箱和删除账户。

### 6.10 ImportBatch / ImportSource

```http
POST   /api/v1/import-batches
GET    /api/v1/import-batches/{id}
POST   /api/v1/import-batches/{id}/sources/text
POST   /api/v1/import-batches/{id}/sources/url
POST   /api/v1/import-batches/{id}/sources/files
DELETE /api/v1/import-batches/{id}/sources/{source_id}
POST   /api/v1/import-batches/{id}/analyze
```

状态：`queued/processing/completed/partial_failure/failed`。

禁止 GET 推进状态或生成业务数据。Demo analyze 的写入语义：

1. POST analyze 幂等生成并保存最终模拟分析结果；
2. 同一事务保存 `started_at`、`demo_processing_at`、`demo_completed_at`；
3. 保存最终 result/case 关联；
4. POST 重试不得生成第二套 Case/Task；
5. GET 完全只读，只根据当前时间和三个时间点动态投影状态；
6. completed 之前隐藏 `case_id/result`；
7. partial/failed 由持久化的 source/result 状态决定；
8. 未来 Worker 只替换执行和状态更新时间，不改变 route 或 DTO。

## 7. 推荐实施顺序

### Phase 0：合同冻结

- 冻结现有测试；
- 最终确认 API contract；
- 确认日期格式、状态 enum、错误 envelope、分页和进度计算口径。

### Phase 1：隔离与安全底座

- settings；
- Demo/Real DB 隔离；
- 最小 migration；
- Demo bootstrap；
- fixture version；
- Demo reset；
- session `token_type`；
- Edge / EvidenceRef owner + Case 校验。

### Phase 2：核心 DTO 与基础 API

- Case 查询/PATCH/聚合；
- Task/Plan DTO；
- overall_progress/current_tasks；
- Profile completeness；
- Privacy API；
- Device revoke；
- Account settings。

### Phase 3：Schedule / Knowledge / Vault

- Schedule CRUD + deterministic preview；
- Knowledge Evidence Provider；
- Vault CRUD + Demo local content provider。

### Phase 4：Dashboard

- 所有统计从当前活动数据库真实计算；
- 不写死 Demo 数字。

### Phase 5：ImportBatch / ImportSource

- 多来源；
- 模拟异步时间投影；
- 幂等 analyze；
- partial failure。

若正式演示脚本确定以多来源导入为第一核心卖点，可将 Phase 5 与 Phase 3 调换。

### Phase 6：前端联调

- 全页面接入同一 API；
- 移除当前 unavailable/construction 状态；
- 保留 loading/empty/error；
- Demo 与 Real 前端调用完全一致。

## 8. 前端修改范围

1. API 层增加可选 envelope/meta 读取方式。
2. CasesView 接搜索、筛选、排序、分页和编辑。
3. Plan 接扩展 Task/Plan DTO；Schedule 替换空时间轴。
4. Import draft 改为服务端 ImportBatch。
5. Knowledge 页接正式 knowledge endpoint。
6. Vault 从占位页改为 CRUD、上传和关联页面。
7. Me/Profile 展示 completeness。
8. SafeShare 使用结构化 findings。
9. Home 读取 Dashboard。
10. Devices 增加撤销，账户设置接新 DTO。

前端类型统一按 API snake_case 定义，避免 camelCase 草案与真实响应分叉。

## 9. 验收条件

基础要求：现有 21 个 pytest 持续通过；新增 mutation 有成功、参数错误、未登录、越权、404 测试；Demo 重启后 mutation 可恢复；owner A 无法读取或修改 owner B 的私有数据；日志和错误响应不包含密码、token、上传原文或敏感 finding。

专项验收：

1. GET 不得修改 ImportBatch 状态、时间点或生成 Case/Task。
2. Demo 用户上传文件后重新读取仍为同一文件，不得变成 fixture。
3. 用户手工修改 deadline 时 `source=user_input` 且 Evidence 列表为空。
4. Knowledge quote 必须真实存在于 fixture 源文件。
5. 无真实概率模型时 confidence 必须为 `null`。
6. Demo reset 后数据库恢复当前 fixture version 的初始 seed。
7. Reset 后 Dashboard 数字恢复。
8. Reset 后 Schedule/Vault/Task mutation 恢复初始状态。
9. 两个 Demo owner 数据完全隔离。
10. `demo.db` 与正式数据库路径相同时启动失败。
11. `DEMO_MODE=false` 时不得读取 `shared/demo` 作为业务 fallback。
12. Edge 两端 Task 必须属于 URL Case。
13. Task/Material EvidenceRef 必须属于同 owner、同 Case。

## 10. 本轮停止点

先完成 Phase 0 和 Phase 1。完成后停止，不提前实现 Phase 2，并汇报修改文件、migration、Demo DB 选择、fixture bootstrap、reset、token_type、Edge/EvidenceRef 修复、新增测试及完整 pytest 结果。
