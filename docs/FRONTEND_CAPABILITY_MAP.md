# 知事 / RuleFlow 前端能力地图

## 2026年10月14日第三批画像交互

ProfileView通过profilePayload读取共享Schema，在请求前校验类型/范围与未知字段；空输入保持null。AnalysisReviewPanel明确标“建议步骤，可取消”。Python/TS采用同一字段契约，布尔或数字字符串不强制参与数值比较。35项前端测试与360/390px保存/错误状态通过，兴趣偏好及事实历史UI尚未实现。

## 2026年10月14日第二批证据预览

EvidenceBottomSheet新增EvidenceViewer，使用access header取documents/{id}/pages/{page}，按page_width/page_height比例绘制行区域。支持错误重试、关闭时释放Blob URL；缺坐标或旧证据只展示文字。已接Case resources行定位字段，并通过360/390px浏览器测试。DOCX/文本暂无图像预览，复杂版面关系尚未实现。

> 更新时间：2026-09-22
> 本文只描述当前代码的真实连通状态。`UI状态 = READY` 只表示页面结构可用，不代表后端能力已完成。
> 后端开发顺序、建议接口和时间不足时的透明演示方案见 `docs/BACKEND_IMPLEMENTATION_PLAN.md`。

## 状态定义

- `CONNECTED`：前端已接入现有真实 API，并有持久化链路。
- `PARTIAL`：存在真实数据或调用链，但字段、恢复、异步处理或端到端能力不完整。
- `MISSING`：当前没有对应后端能力。
- `LOCAL_ONLY`：仅在设备/浏览器本地处理，不会保存为账户服务数据。
- `DEMO_ONLY`：只存在明确标记且与账户隔离的演示数据。

## 能力表

| 前端功能 | 页面 | UI状态 | 数据来源 | 后端状态 | 后续需要 |
| ---- | -- | ---- | ---- | ---- | ---- |
| 工作台统计、今日任务与最近事项 | `HomeView` `/home` | READY | 登录时 `/api/v1/dashboard`，未登录时显式 Demo 最近事项 | CONNECTED / DEMO_ONLY | 可后续增加提醒与个性化排序 |
| 事项列表 | `CasesView` `/cases` | READY | `/api/v1/cases` 或显式 Demo | CONNECTED | 可后续增加游标继续加载和更多组合筛选 |
| 执行计划 · 行动步骤 | `PlanView` `/plan?tab=steps`（`/plan` 默认） | READY | `/api/v1/cases/{id}/plan` | CONNECTED | 可后续增加任务内容编辑与状态活动记录 |
| 任务状态修改 | `PlanView`、旧 Flow 页 | READY | `PATCH /api/v1/tasks/{id}`；Demo 仅本地体验 | CONNECTED / DEMO_ONLY | 服务端撤销语义、操作记录（如产品需要） |
| 事项选择 Bottom Sheet | `PlanView` | READY | 当前 `cases.items` | CONNECTED / DEMO_ONLY | 无独立后端需求 |
| 多来源导入入口 | `ImportView` `/imports/new` | READY | 当前选择 + ImportBatch API + Android PendingImports | CONNECTED | 可后续增加更多文件格式 |
| 粘贴文字导入 | `ImportView` → `ImportSourcesView` | READY | `POST /api/v1/import-batches/{id}/sources/text` | CONNECTED | 可后续增加超长正文分块策略 |
| 网页链接导入 | `ImportView` → `ImportSourcesView` | READY | `POST /api/v1/import-batches/{id}/sources/url` | CONNECTED | 附件逐项确认仍可扩展 |
| 文件导入 | `ImportView` → `ImportSourcesView` | READY | `POST /api/v1/import-batches/{id}/sources/files` | CONNECTED | 当前保存 metadata 与提取文本，不保存原文件 |
| 从其他 App 分享 | `ImportView` | PARTIAL | Android `PendingImports` 插件；Web 提供移动端系统分享指引并保留粘贴/文件入口 | PARTIAL | iOS/其他平台 Share Extension；队列恢复与错误状态 UI |
| 导入来源确认 | `ImportSourcesView` `/imports/:id/sources` | READY | 持久化 ImportBatch / ImportSource | CONNECTED | 可后续增加来源重新抓取 |
| 多来源合并为一个事项 | `ImportSourcesView`、`ImportProgressView` | READY | Batch analyze 合并成功来源并保留失败来源 | CONNECTED | 可后续替换为真实 Worker |
| 批次分析进度 | `ImportProgressView` `/imports/:id/progress` | READY | GET ImportBatch 的只读时间状态投影 | CONNECTED | 可后续接入 Worker 事件推送 |
| 导入隐私预览 | `ImportView` | READY | `services/privacy.ts` 本地规则 | LOCAL_ONLY | 更完整检测规则；结构化 finding API；审计策略 |
| 结构化解析结果 | `AnalysisResultView` `/cases/:id`、`/cases/:id/analysis` | READY | Case、resources、plan 现有 API | PARTIAL | 正文、时间、地点、人员等统一结构化 DTO；字段级 Evidence 关系 |
| 事项上下文头 | `CaseContextHeader` | READY | Case 的 title/category/relevance/deadline（仅有值时显示） | CONNECTED | 无独立后端需求 |
| 相关性判断 | `RelevanceView`、`RelevanceCard` | READY | Case `relevance` 与 resources `facts` | CONNECTED / PARTIAL | 多条规则合并策略、可解释判断详情、缺失画像字段清单 |
| 个人画像编辑 | `ProfileView` `/profile` | READY | `/api/v1/profile` | CONNECTED | 可后续扩展字段与校验规则 |
| 资料完整度 | `MeView`、`ProfileView` | READY | `/api/v1/profile/completeness` | CONNECTED | 规则可随产品字段扩展 |
| 关键时间 | `AnalysisResultView` | READY | Case `deadline/deadline_source/deadline_evidence_ids` | CONNECTED / PARTIAL | 更多时间类型 |
| 材料要求 | `AnalysisResultView`、旧 Materials 页 | READY | resources `materials` | CONNECTED | 材料状态语义完善；不要与个人材料库混淆 |
| 个人材料库 / Vault | `VaultView` `/vault` | READY | Vault CRUD/content API；owner-scoped 本地内容 Provider | CONNECTED | 晋级后可替换为对象存储 Provider |
| Evidence 原文依据 | `EvidenceLink`、`EvidenceBottomSheet`、Sources 页 | READY | resources `evidence` 与各资源的 `evidence_ids` | CONNECTED | 时间等字段级引用；多引用切换；PDF 定位能力（后端真实提供后） |
| 当前通知规则依据 | `KnowledgeEvidenceView` `/cases/:id/knowledge`、兼容 `/rules` | READY | resources `rules` + `evidence` | CONNECTED | 多 Evidence 展示与规则 AST 的面向用户解释 |
| 校园知识库 / 外部规则 | `KnowledgeEvidenceView` | READY | Knowledge Evidence API + Provider；Demo 条款可追溯 | DEMO_ONLY / CONNECTED | Real mode 需替换真实 Knowledge Provider |
| 外部依据 DTO | `types/product.ts`、`KnowledgeEvidenceView` | READY | 来源、版本、quote、reference、match metadata | CONNECTED | `confidence` 在无概率模型时保持 null |
| 时间排程 / Schedule | `PlanView` + `PlanSchedule` `/plan?tab=schedule&case=:id` | READY | Schedule CRUD + deterministic preview + SQLite 持久化 | CONNECTED | 当前不同步第三方 Calendar |
| Schedule DTO | `types/product.ts` | READY | busy/course/task time block 与 Case/Task 关联 | CONNECTED | 可后续替换 Calendar/Availability Provider |
| 隐私检测与安全分享 | `SafeShareView` `/privacy`；可用 `?case=:id` 带入事项 | READY | `/api/v1/privacy/analyze`；用户输入、TXT 或 Evidence | CONNECTED | 姓名/邮箱/学号/地址等扩展规则 |
| 脱敏前后预览 | `SafeShareView` | READY | 结构化 findings 与 `redacted_text` | CONNECTED | 可后续增加逐项接受/忽略 |
| 复制安全版本 | `SafeShareView` | READY（有条件） | 只复制真实生成且无已知未遮盖类型的文本 | LOCAL_ONLY | 剪贴板失败提示的更多平台适配 |
| 系统分享安全版本 | `SafeShareView` | READY（有条件） | Web Share API；只分享真实脱敏文本 | LOCAL_ONLY | Capacitor 原生 Share 适配（如需覆盖更多设备） |
| 统一 Empty/Loading/Offline | `AppState` | READY | 页面当前真实状态 | LOCAL_ONLY | 可继续补充错误码到状态映射 |
| 统一 Bottom Sheet | `AppBottomSheet` | READY | 前端组件；已用于 Case Selector 与 Evidence | LOCAL_ONLY | 焦点循环和更完整的无障碍弹窗管理 |
| 登录、注册、验证、重置 | 旧 `Page` Auth routes | READY | 现有 Auth API | CONNECTED / PARTIAL | 生产邮件投递与更完整账户设置 |
| 登录设备 | `DevicesView` `/settings/devices` | READY | `/api/v1/auth/sessions`、`DELETE /sessions/{id}` | CONNECTED / PARTIAL | 可后续细化设备识别与 last_used_at 更新 |
| 账户设置 | `AccountSettingsView` `/settings/account` | READY | `/api/v1/account/settings` | CONNECTED | 当前仅显示名称、locale 和 timezone |
| Demo / 账户隔离 | 主页面、Case 相关页 | READY | 无会话时只加载 `shared/demo`，并显示“演示”标识 | DEMO_ONLY / CONNECTED | 保持正式路径不自动填充 fixture |

## 新页面与真实边界

### 导入链路

`/imports/new` 在用户确认隐私范围后把实际选择保存为 ImportBatch；`/imports/:id/sources` 从服务端恢复来源并支持删除、补充和独立错误展示。文字、URL 与文件可以在同一批次中合并，分析状态页通过只读 GET 恢复 queued、processing 和最终结果。

### 解析与依据链路

`/cases/:id/analysis` 复用 Case/resources 数据。规则、材料要求、步骤通过 `evidence_ids` 找回真实 Evidence。Case deadline 通过 `deadline_source/deadline_evidence_ids` 区分文档解析与用户输入，手工修改不会伪造 Evidence。

### Plan 与 Schedule

Plan 在同一一级页面内提供“行动步骤 / 日程安排”双 Tab。行动步骤读取 `/plan` API 并通过 Task PATCH 保存状态；日程安排读取持久化 time block，支持预览、确认、编辑与删除。旧 `/cases/:id/schedule` 会跳转到 `/plan?tab=schedule&case=:id`。

`GET /api/v1/cases/{id}/export.ics` 仍保留为文件导出；Schedule API 独立管理课程、忙碌和任务 time block。当前不读取设备或第三方日历。

### 安全分享

当前是全局 `LOCAL_ONLY` 工具：身份证号、手机号、银行卡号可以被现有规则实际遮盖；邮箱和疑似学号只会提示，页面会禁用“安全版本”操作。具体事项可通过 `/privacy?case=:id` 自动带入第一条真实 Evidence，旧事项隐私 URL 会兼容跳转。

## 下一轮后端接口优先级

1. **字段级结构化解析 DTO + Evidence 关系**：统一时间、地点、人员、材料、任务、规则字段，并让每个字段可追溯。
2. **真实外部 Provider**：晋级后按需替换 Knowledge、Vault Content 与 Calendar Provider。
3. **账户隐私设置**：同步范围、保留期限、数据导出与清除。

以上是能力优先级，不是可直接编码的请求/响应合同。后端实现应以 `BACKEND_IMPLEMENTATION_PLAN.md` 的接口草案和验收条件为起点，再由前后端共同确认字段。
## 2026年10月14日增量确认能力

`AnalysisReviewPanel.vue` 已接入 `GET cases/{id}/reviews`、`POST reviews/prepare`、`POST confirm`；允许选择动作、日期候选、人工日期或明确不设截止，同意前按钮禁用。过期版本显示错误并要求重读/重新同意。解析结果与执行计划空状态连接到确认入口。

日期/行动候选、确认后最小编译及Task/日程门禁本轮已实现。360/390px Mock API浏览器交互通过；原图/PDF高亮、真实知识入库/检索、文件永久脱敏、完整排程草案仍未完成。详见 `SMART_RECOGNITION_SUBFUNCTIONS.md`，不将本节的确认能力扩大为完整智能识别完成。


## 2026-10-14 最新实现（替代早期未完成条目）

解析页：候选/依赖确认、原图高亮、历史快照及重新分析。原件隐私页：扫描、选择、明确同意、永久副本下载。来源页：网页附件候选、单项确认。画像页：共享类型、排名有效期、填写历史与独立软关注分类。知识页：真实资料入库与有来源摘录。日程页：耗时/拆分设置、工作时段/限额/缓冲、按周课程、锁定与整份草稿确认。浏览器测试使用Mock API，不能代替实体设备或真实模型验收。
