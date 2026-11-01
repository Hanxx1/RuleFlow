# 知事 RuleFlow 功能与代码审计

> 后端基线审计：2026-09-20；前端基线复核：2026-09-22。
> 本文保留 Phase 0 之前的扫描证据与当时缺口，不再作为 Phase 1–3 完成后的能力状态表。
> 当前连通状态以 `FRONTEND_CAPABILITY_MAP.md`、`API.md` 和 `BACKEND_IMPLEMENTATION_PLAN.md` 为准。

## 1. 状态口径

| 状态 | 含义 |
|---|---|
| ✅ 已完整实现 | 在当前范围内有前端、API/业务、持久化和必要的代码/测试证据，调用链连通 |
| 🟡 部分实现 | 核心代码存在，但字段、平台、异常、交互或端到端链路不完整 |
| 🔵 UI/入口存在 | 路由、菜单或文案存在，但底层未实现或页面没有接入已有 API |
| ⚪ 仅 Mock / Demo | 只对固定样例数据生效，不代表真实用户功能 |
| ❌ 未实现 | 未找到可执行的实现链路 |
| ❓ 无法确认 | 静态证据不足，需实机、外部服务或构建环境复验 |

UI 重构映射另用 `READY / PARTIAL / MISSING / MOCK`；其含义与上表对应。

## 2. 审计范围与重要边界

已递归检查以下内容：

- 根目录 `README.md`、`.env.example`、`compose.yaml`、`AGENTS.md`、两份产品/开发规格。
- `docs/` 内现有 API、系统设计、部署、隐私、迁移、验收与已知限制文档。
- Vue/TypeScript 移动前端的路由、页面、Pinia store、service、PWA 缓存与测试。
- Android Capacitor 容器、分享 Activity、原生桥、Manifest 和 Gradle 配置。
- iOS Capacitor 工程和 Share Extension 源码。
- HarmonyOS ArkTS/ArkUI 工程基线。
- FastAPI 全部路由、SQLite DDL/SQL、认证、解析、OCR、规则引擎、LLM adapter、隐私脱敏和测试。
- shared schema、规则测试向量、Demo/fixture 数据及移动端副本。

本次复核开始时工作区干净。当前仓库没有 `deliverables/Zhishi-RuleFlow-debug.apk`，因此旧文档中“已生成 APK”只是历史记录，不是当前可交付文件的证据。

## 3. 整体技术栈与架构

### 3.1 技术栈

| 层 | 当前实现 |
|---|---|
| 主前端 | Vue 3 + TypeScript + Vite 5 + Vue Router + Pinia；引入 Ionic CSS，但页面主体是普通 Vue/HTML/CSS，未使用 Ionic 组件体系 |
| Android/iOS | Capacitor 6 包装同一套 Vue Web UI |
| Android 原生 | Java Activity + Capacitor Plugin，用于系统分享接收和 pending import 队列 |
| iOS 原生 | Swift Share Extension 源码，但未加入 Xcode target，主 App 也没有读 App Group 队列的对应桥 |
| HarmonyOS | ArkTS/ArkUI 独立工程基线；当前页面仅规则引擎验证和导入占位文案 |
| 后端 | Python FastAPI + Pydantic 2 + httpx |
| 数据库 | Python `sqlite3`；启动时用 `CREATE TABLE IF NOT EXISTS` 直接建表 |
| 认证 | Argon2 密码哈希 + 不透明 token + HMAC-SHA256 token hash |
| 文档解析 | pypdf、python-docx、openpyxl、xlrd、BeautifulSoup |
| OCR | RapidOCR ONNX + Pillow + NumPy；扫描 PDF 用 PyMuPDF 渲染后 OCR |
| AI | OpenAI-compatible `/chat/completions` adapter，可配 DeepSeek；未配时走本地规则 |
| 测试 | pytest/FastAPI TestClient + Vitest；本次文档更新完成后以第 9.5 节记录的复验结果为准 |

### 3.2 前端架构

- `mobile/src/main.ts` 创建 Vue App、Pinia 和 Router，启动时尝试读原生分享队列，并注册 Service Worker。
- `mobile/src/App.vue` 提供 `RouterView` 和四项固定底部导航；欢迎页和 Auth 页面不显示 Bottom Navigation。
- 四个主页面和新增产品页已拆为 `HomeView`、`CasesView`、`PlanView`、`MeView`、`ImportView`、`ImportSourcesView`、`AnalysisResultView`、`RelevanceView`、`KnowledgeEvidenceView`、`SafeShareView`。`Page.vue` 只继续承载 Auth、画像、设备和未独立拆分的工具/占位页。
- 公共组件已经覆盖事项卡、上下文头、Timeline、Bottom Sheet、Evidence、统一状态和设置分组。组件完成不等于对应后端能力完成。
- `mobile/src/router.ts` 保留旧 URL；`/cases/:id/schedule` 和 `/cases/:id/privacy` 分别兼容跳转到 `/plan?tab=schedule&case=:id` 与 `/privacy?case=:id`。
- 有效 store 是 `account.ts`、`cases.ts` 和 `importDraft.ts`。`stores/app.ts` 未被生产代码引用，属于遗留实现。
- API 仍集中在 `mobile/src/services/api.ts`；`privacy.ts` 是本地检测，`share.ts` 连接原生分享队列，`types/product.ts` 只是未来 DTO 草案。当前没有 repository 抽象或持久化会话适配层。

### 3.3 状态管理

- 账户、设备列表：Pinia `useAccountStore`。
- 事项列表、当前事项、资源、执行计划：Pinia `useCasesStore`。
- 导入来源草稿：Pinia `useImportDraftStore`，仅内存保存，刷新后不可恢复。
- 页面表单、错误、加载状态：各独立 View 内的 Vue `ref/computed`；Auth 和部分旧工具页仍在 `Page.vue`。
- access/refresh token：`api.ts` 模块内存变量；刷新 App/WebView 即丢失，没有 Keychain/Keystore/Preferences 恢复。
- 本机画像和教程标记：`localStorage`。
- Demo 任务状态：操作时写 `zhishi-demo-tasks`，但加载 Demo 时没有读回，所以刷新后不会恢复。

### 3.4 后端架构

- 大部分 API、DDL、SQL、导入编排和分析持久化集中在 `server/app/main.py`。
- 认证和数据库连接在 `server/app/auth.py`。
- 格式解析在 `server/app/parsing.py`，三值规则在 `rules.py`，LLM 适配和输出校验在 `ai.py`，脱敏在 `privacy.py`。
- 没有 ORM、正式 migration、worker 进程、对象存储、SMTP 或调度器。
- `analysis_jobs` 虽持久化，但实际分析在 HTTP 请求里同步完成，不是后台任务系统。

### 3.5 持久化方式

| 数据 | 存储 | 事实 |
|---|---|---|
| 账户、会话、验证 token | SQLite | `users/sessions/verification_tokens` |
| 事项、事实、证据、规则、任务、DAG 边、材料要求 | SQLite | 按 `owner_id` 存储；部分外键/一致性只靠代码 |
| import/job/analysis metadata | SQLite | 可记录，但 job 无 worker |
| 原始上传文件 | 不持久化 | 请求内解析后丢弃 raw bytes；只保留抽取文本 evidence |
| 个人材料文件 | 无 | 当前 `materials` 表只是“需要哪些材料” |
| 本机画像 | localStorage | 未登录时保存；不会自动迁移到账户 |
| Demo | 静态 JSON + Service Worker cache | 明确的模拟/脱敏样例 |
| Android 待确认分享 | App 私有文件 + SharedPreferences | 读取后前端上传；`clearPending` 只清队列，没有删除已复制文件 |
| 同步日志 | SQLite `sync_*` | 独立变更日志，没有与主业务表或前端接通 |

### 3.6 核心数据模型关系

```text
User
 ├─ Session / VerificationToken
 ├─ Profile Fact (case_id = NULL)
 ├─ Import ─ AnalysisJob
 └─ Case
     ├─ Case Fact
     ├─ Evidence (Block)
     ├─ Rule (AST + evidence_ids)
     ├─ Task (status + deadline + evidence_ids)
     │   └─ TaskEdge (before_task_id -> after_task_id)
     ├─ Material requirement (title/state/evidence_ids)
     ├─ Conflict record
     └─ AnalysisMetadata
```

注意：`Import` 表没有 `case_id`，`AnalysisJob` 也没有 `case_id`；导入返回了 `case_id`，但后续无法单凭 import/job 表反查其事项。多数表也没有声明完整外键。

## 4. 页面与路由事实

| 路由 | 真实状态 | 说明 |
|---|---|---|
| `/welcome` | 🟡 | 欢迎页可用，可去登录或 Demo |
| `/auth/login` | 🟡 | 登录连通，但会话不持久，无路由守卫 |
| `/auth/register` | 🟡 | 可注册；生产无 SMTP，开发返回 token |
| `/auth/verify` | 🟡 | token 验证连通 |
| `/auth/reset` | 🟡 | 开发 token 流程连通；生产邮件未实现 |
| `/home` | 🟡 | 独立工作台；导入入口、四个快捷入口和最近 4 个事项；未登录明确显示 Demo |
| `/imports/new` | 🟡 | 独立多来源采集 UI；支持文字、URL、受支持文件和 Android PendingImports，提交前会校验登录、数量、扩展名和大小 |
| `/imports/sources`、`/imports/:id/sources` | ✅ | 当前选择经同意后保存为 ImportBatch；服务端来源列表支持恢复、删除、补充和独立错误展示 |
| `/imports/:id/progress` | ✅ | 只读轮询 Batch 状态，展示 queued/processing/completed/partial_failure/failed，并可打开生成事项 |
| `/imports/:id/sources` | 🔵 | 兼容进入同一来源确认页，但没有按 import id 从后端恢复来源的 API |
| `/imports/:id/progress` | 🟡 | 可读 job 并调 retry/cancel，但没有 worker，进度非真实异步进度 |
| `/imports/:id/review` | 🔵 | 路由存在，无结果确认实现 |
| `/cases` | 🟡 | 独立事项列表；“全部”真实可用，其余筛选明确禁用；无搜索/服务端筛选/排序/分页 |
| `/cases/new` | 🟡 | 登录用户可手工创建标题+分类；不可填截止日期等 |
| `/cases/:id`、`/cases/:id/analysis` | 🟡 | 结构化解析结果页；聚合现有 Case/resources/plan，展示真实相关性、时间、材料要求、步骤、规则和 Evidence；缺失字段显示待核对 |
| `/cases/:id/relevance` | 🟡 | 使用现有 Case relevance 与 facts；不在前端重新计算相关性 |
| `/cases/:id/knowledge`、`/cases/:id/rules` | 🟡 | 当前通知规则与 Evidence 已连接；外部校园知识库显示未接入空状态 |
| `/cases/:id/questions` | 🔵 | 路由存在，无补问表单 |
| `/cases/:id/materials` | 🟡 | 只读材料要求列表，不是材料库 |
| `/cases/:id/flow` | 🟡 | 保留旧执行流程入口；真实读取 DAG 并更新任务状态，主 Timeline 体验已迁移到 `/plan` |
| `/cases/:id/sources` | 🟡 | 列出 evidence 文本；没有文档版本/附件/更新 |
| `/cases/:id/conflicts` | 🔵 | 路由存在；后端表存在但无写入/处理 API |
| `/cases/:id/schedule` | 🟡 | 兼容跳转到 `/plan?tab=schedule&case=:id` |
| `/cases/:id/privacy` | 🟡 | 兼容跳转到 `/privacy?case=:id` |
| `/plan` | 🟡 | 独立 Plan 页面；当前事项卡片作为选择器，行动步骤接真实 plan/PATCH；离线示例展示带 EvidenceRef 的模拟周日程，账户模式仍为真实未接入状态 |
| `/privacy` | 🟡 | 全局本地隐私工具；文字/TXT/真实 Evidence 可检测，当前仅可靠遮盖身份证、手机号和银行卡号，不持久化 |
| `/vault` | 🔵 | 菜单/路由存在，没有材料文件功能 |
| `/inbox` | 🔵 | 路由占位 |
| `/me` | 🟡 | 独立个人中心，按个人资料、工具与安全、账户与支持分组；入口会诚实显示未实现能力 |
| `/profile` | 🟡 | 画像查询/保存可用；本机画像不会影响当前 Demo 求值 |
| `/settings/privacy` | 🔵 | 路由占位 |
| `/settings/devices` | 🟡 | 可列出未撤销 session；不能按设备撤销 |
| `/settings/notifications` | 🔵 | 路由占位 |
| `/help` | 🟡 | 有现有能力说明与常见问题；反馈提交/日志上传未实现 |
| `/about` | 🟡 | 有版本、数据原则和判断原则说明；不是远端配置页 |

## 5. 功能事实表

### A. 通知导入

| 功能 | 状态 | 前端 | 后端/API | 持久化 | 证据文件 | 备注 |
|---|---|---|---|---|---|---|
| 粘贴文本 | ✅ | `ImportView` 采集并完成本地隐私确认，`ImportSourcesView` 管理持久化来源 | `POST /api/v1/import-batches/{id}/sources/text` | Batch、Source、Case、Evidence、analysis 入 SQLite | `importBatch.ts`; `main.py:add_import_text_source` | 旧 `/imports/text` 继续兼容 |
| PDF | 🟡 | file input 接受 `.pdf` | `/imports/files`; pypdf，无文本页转 OCR | 只存抽取 evidence，不存原件 | `parsing.py:parse_bytes`; `main.py:files` | 未见 PDF 自动化解析测试；无页数/解压资源限制 |
| PNG/JPEG 图片 | 🟡 | file input 接受 | RapidOCR | 只存 OCR evidence | `parsing.py:_ocr`; `test_parsing.py` | 测试只是空白 PNG 路径烟测；无像素级脱敏/EXIF 清理 |
| TXT/HTML | 🟡 | accept 中含 `.txt/.html` | 直读/BeautifulSoup | 只存 evidence | `main.py:ALLOWED`; `parsing.py` | HTML 未保留结构，只取纯文本 |
| DOCX | 🟡 | 接受 `.docx` | python-docx | 只存 evidence | `parsing.py`; `test_parsing.py` | 只读 paragraph，表格/页码/附件未处理 |
| 旧 DOC | ❌ | 前端不再宣称支持，也不在 `accept` 中 | MIME 不在 `ALLOWED`，无 parser | 无 | `ImportView.vue`; `main.py:ALLOWED` | 应先另存为 DOCX/PDF；不是现有能力 |
| XLSX | 🟡 | 接受 | openpyxl | 只存 evidence | `parsing.py`; `test_parsing.py` | 读单元格值，不保留格式/合并语义 |
| XLS | 🟡 | 接受 | xlrd | 只存 evidence | `parsing.py` | 无对应测试 |
| URL | 🟡 | URL 输入 | Batch URL Source，复用 `fetch_public` 安全抓取 | Source metadata、提取文本与 Evidence | `main.py:fetch_public/add_import_url_source` | 有 SSRF 基线保护；DNS 检查与真实连接之间仍有重解析/TOCTOU 风险 |
| URL 附件发现 | 🟡 | 无附件选择页 | 从 HTML 中找最多 10 个特定扩展名链接 | 不持久化附件候选 | `main.py:import_url` | 只返回 URL，没有后续选择/下载 API，链路中断 |
| Android 系统分享 | 🟡 | 启动读 pending queue 并跳导入页 | Java 桥读 SharedPreferences | 私有文件+队列 | `ShareReceiverActivity.java`; `PendingImportsPlugin.java`; `share.ts` | 代码链连通，但无本轮真机证据；清队列不清复制文件 |
| iOS 系统分享 | 🔵 | Web 只认 Capacitor `PendingImports` | Share Extension 源码存在 | App Group 队列设计 | `ShareViewController.swift`; `project.pbxproj` | Extension 未加 target；无 iOS `PendingImports` 桥；字段还用 `local_ref`而 Web 期望 `local_path` |
| HarmonyOS 分享/导入 | 🔵 | 按钮只改文案 | 无解析/API 接入 | 无 | `harmony/.../Index.ets`; `module.json5` | Want action 已声明，但未处理 Want 数据 |
| 文件数量/大小限制 | ✅ | 前端预检最多 10 个、单个 20MB | 最多 10 个，单个 20MB；URL 10MB | import 记录 | `ImportView.vue:chooseFiles`; `main.py:files/fetch_public` | Android receiver 仍有独立限制链 |
| MIME/类型限制 | 🟡 | accept 与扩展名白名单和后端支持范围一致 | 服务端 Content-Type 白名单校验 | 记 MIME/hash | `ImportView.vue`; `main.py:ALLOWED/files` | 服务端仍信任客户 Content-Type，未验证 magic bytes |
| 上传/解析状态 | ✅ | 独立 `ImportProgressView` 展示批次状态并可刷新恢复 | GET Batch 只读投影时间状态 | SQLite | `ImportProgressView.vue`; `_batch_projected_state` | 当前无 Worker，未来可替换执行方式而不改 DTO |
| 失败处理 | ✅ | 每个来源展示独立错误；成功来源仍可生成事项 | `partial_failure/failed`，可删除失败来源后重新分析 | SQLite | Batch source/analyze routes | 同一 revision analyze 幂等 |

### B. 通知智能解析

| 字段/能力 | 状态 | 真实来源 | 持久化 | 证据 | 备注 |
|---|---|---|---|---|---|
| 标题 | 🟡 | 用户输入；否则文本首个非空行/文件名 | `cases.title` | `title_from`; import endpoints | LLM 也返回 title，但代码没把 AI title 写回 Case |
| 正文 | 🟡 | 原文或解析/OCR 文本 | `evidence.text` | `parse_bytes`; import endpoints | 未建独立 body 字段，以 evidence blocks 形式保存 |
| 时间/截止日期 | 🟡 | 文本导入用一个简单正则；LLM 可给任务 deadline | `cases.deadline`; `tasks.deadline` | `import_text`; `TaskCandidate` | 只文本导入自动写 Case deadline；URL/文件不写；无归一化、时区、相对日期/多日期逻辑 |
| 地点 | ❌ | 无提取字段 | 无 | 无模型/API/schema | 即使 LLM 理解到，`AIAnalysis` 也不允许输出 |
| 相关人员/联系人 | ❌ | 无 | 无 | 无模型/API/schema | MISSING |
| 所需材料 | 🟡 | 本地只搜 6 个固定关键词；可选 LLM 生成 candidate | `materials` | `_local_candidates`; `AIAnalysis`; `_persist_analysis` | 是“材料要求”，不是用户已上传材料 |
| 待办事项 | 🟡 | 本地总是生成 2 个通用步骤；可选 LLM 候选 | `tasks/task_edges` | `_local_candidates`; `_persist_analysis` | 本地步骤并非通知精准提取；所有 evidence 都指向全文块 |
| 分类 | 🟡 | 本地关键词分类 | `cases.category` | `category_from` | 文件导入直接写 `other`；AI category 没有回写 Case |
| 优先级 | ❌ | 无 | 无 | 无字段 | MISSING |
| 适用条件/规则 | 🟡 | 4 类本地正则或可选 LLM | `rules.ast_json` | `_local_candidates`; `ai.py` | 本地基线很有限；LLM 候选经 AST/EvidenceRef/短引校验 |
| 资格判断 | 🟡 | 确定性三值求值 | `cases.relevance` | `rules.py:evaluate`; `evaluate_case` | 实际只把第一条规则的值当事项 relevance，没有明确 scope rule 标识 |
| 分析摘要/待核对问题 | 🟡 | 本地固定摘要/问题或 LLM | `analysis_metadata` | `analyze_case`; `case_resources` | 页面只展示，不能在 questions 页回答 |
| 冲突识别 | 🔵 | 数据表和路由名存在 | `conflicts` 空表 | `database`; `router.ts` | 无检测、写入、处理 API/UI |
| AI/LLM 真实调用 | 🟡 | 配置环境变量后调 OpenAI-compatible API | analysis metadata | `ai.py`; `analyze_case`; `test_ai.py` | 本轮未配置/联网验证；默认不调 AI |

### C. 事项

| 功能 | 状态 | 前端 | 后端/API | 持久化 | 证据文件 | 备注 |
|---|---|---|---|---|---|---|
| 通知生成事项 | ✅ | 来源确认后 analyze，进度页打开结果 | ImportBatch 把多个成功来源合并为一个 Case | SQLite | `ImportProgressView.vue`; `analyze_import_batch` | 失败来源保留错误并形成 partial failure |
| 手动创建 | 🟡 | 标题+分类 | `POST /cases` | SQLite | `Page.vue:createCase`; `create_case` | API 可接 deadline/status，UI 未提供 |
| 查看列表/详情 | ✅ | 已连通 | `GET /cases`, `/cases/{id}` | SQLite | `cases.ts`; `main.py` | 账户数据 owner-scoped |
| 编辑事项 | ❌ | 无 | 无 PATCH/PUT Case | 无 | endpoint index | MISSING |
| 删除/归档/回收站 | ❌ | 无 | 无端点 | 无 | endpoint index | `status!='deleted'` 查询暗示设计，但没有写入链路 |
| 事项状态更新 | ❌ | 无 | 无 Case status API | 无 | endpoint index | 创建时可传 status，之后不可改 |
| 分类 | 🟡 | 手动创建时可选 7 类 | `cases.category` | SQLite | `Page.vue`; `CaseIn` | API 不校验枚举，与 shared schema 仍可能不一致 |
| 截止日期 | 🟡 | 详情可显示 | Case 字段，文本简单抽取 | SQLite | `cases.deadline`; `import_text` | 无编辑/统一日期语义 |
| 剩余时间/过期 | ❌ | 无 | 无计算 | 无 | 无代码 | MISSING |
| 待办子任务 | 🟡 | `/plan` Timeline 与旧 flow 页 | tasks + edges API | SQLite | `PlanView.vue`; `TaskTimeline.vue`; `cases.ts`; `main.py` | 可自动或 API 创建，但 UI 不能手工增删改 |
| 完成进度 | ❌ | 无 | 无聚合字段/统计 | 无 | 无代码 | 可从 task status 派生，但当前未做 |
| 搜索/筛选/排序 | ❌ | 无 | 无查询参数 | 无 | `GET /cases` 只按 updated_at | MISSING |
| “已完成事项” | ❌ | 无 | Case 状态不会根据任务自动变化 | 无 | `patch_task` | 任务全 done 不会完成 Case |

### D. 执行计划 / RuleFlow

| 功能 | 状态 | 前端 | 后端/API | 持久化 | 证据文件 | 备注 |
|---|---|---|---|---|---|---|
| `通知 → 事项 → 步骤` | 🟡 | 导入后可在解析结果与 `/plan` Timeline 查看 | import → analyze → persist tasks/edges | SQLite | `import_*`; `analyze_case`; `_persist_analysis`; `PlanView.vue` | 真实链路存在，默认本地步骤仅两个通用模板 |
| 自动生成步骤 | 🟡 | 可显示 | 本地固定步骤或 LLM candidate | SQLite | `_local_candidates`; `AIAnalysis` | 存在但准确性/覆盖面不足 |
| 步骤顺序 | ✅ | 按返回顺序渲染 | DAG 存边，`plan` 拓扑排序，加边防环 | SQLite | `edge`; `plan`; tests | 自动分析只生成线性链，API 可表示更一般 DAG |
| 步骤状态 | ✅ | Timeline 通过紧凑状态操作选择 todo/in_progress/done/skipped | `PATCH /tasks/{id}` | SQLite | `TaskTimelineItem.vue`; `setTask`; `patch_task` | 账户模式真持久化 |
| 完成一步/撤销完成 | ✅ | 状态可任意来回切换 | PATCH task | SQLite | 同上 | 无状态迁移限制或审计记录 |
| Demo 步骤持久化 | ⚪ | 当次运行可改 | 不调 API | localStorage 写了但不读 | `cases.ts:setTask/loadPlan` | 刷新丢失，不是可靠持久化 |
| 当前步骤 | ❌ | 无特殊标记 | 无派生逻辑 | 无 | 无代码 | MISSING |
| 步骤预计耗时 | ❌ | 无 | 任务模型无 duration | 无 | tasks DDL | MISSING |
| 步骤截止时间 | 🟡 | 可显示 | `tasks.deadline` | SQLite | Task model/UI | LLM 可给，本地生成的任务不继承 Case deadline |
| 步骤需要的材料 | ❌ | 无 | task 和 material 之间无关联表/字段 | 无 | DDL | MISSING |
| 整体进度 | ❌ | 无 | 无聚合逻辑 | 无 | 无代码 | MISSING |
| 相关文件 | ❌ | 无 | 原文件不持久化，task 无 file relation | 无 | DDL/import code | 只能通过 evidence id 看抽取文本 |
| 当前事项选择 | 🟡 | `/plan` 当前事项卡片 + Bottom Sheet，可通过 query 保留选中 Case | 仍逐 Case 调 plan API | 前端路由 query，不是账户持久化偏好 | `PlanView.vue`; `AppBottomSheet.vue` | 选择体验已实现；无跨事项任务聚合 |
| 日程安排 | 🔵 | `/plan?tab=schedule` 有周日期条；离线示例含课程、忙碌、任务时间块及 EvidenceRef，账户模式为空时间轴 | 无 Schedule/Calendar API；仅有 Case ICS 导出 | Demo JSON | `PlanSchedule.vue`; `main.py:export_ics` | 示例不持久化、不混入账户；真实导入、忙碌时间保存和自动安排仍未实现 |
| 跨事项计划 | 🔵 | 可切换当前 Case，但不聚合多 Case task | 无跨 Case task API/排序 | 无 | `PlanView.vue`; endpoint index | 不支持今日/本周/逾期/冲突 |

### E. 材料库

| 功能 | 状态 | 前端 | 后端/API | 持久化 | 证据文件 | 备注 |
|---|---|---|---|---|---|---|
| 材料要求抽取/列表 | 🟡 | 解析结果页和旧 Case materials 页只读 | analysis 自动写，也有 POST API | SQLite `materials` | `_persist_analysis`; `case_resources`; `MaterialRequirementList.vue` | 存的是标题、状态、evidence ids，不是文件 |
| 个人材料上传 | ❌ | `/vault` 占位 | 无 API | 无 | endpoint index | MISSING |
| 材料文件保存 | ❌ | 无 | 无 file/blob/object storage | 无 | DDL/已知限制 | MISSING |
| 材料列表/分类/搜索/删除 | ❌ | 无 | 无 | 无 | 无代码 | MISSING |
| 与事项关联 | 🟡 | Case 页下可看 | `materials.case_id` | SQLite | materials DDL | 只有材料要求与单个 Case 关联 |
| 与步骤关联 | ❌ | 无 | 无 task-material relation | 无 | DDL | MISSING |
| 材料状态更新 | ❌ | 无 | 无 PATCH material | 已存初始 state 但无更新链路 | endpoint index | MISSING |

### F. 个人画像

| 功能 | 状态 | 前端 | 后端/API | 持久化 | 证据文件 | 备注 |
|---|---|---|---|---|---|---|
| 画像字段 | 🟡 | UI：`student_type,enrollment_year,college,major,rank_percent,team_size,graduation_year` | 还接受 `class_name,certificate_level,role,moral_bonus_items` | SQLite facts / localStorage | `Page.vue`; `PROFILE_FIELDS` | UI 未覆盖所有后端字段 |
| 用户编辑 | ✅ | profile form | `GET/PUT /profile` | 账户 SQLite；本机 localStorage | `saveProfile`; `get/put_profile` | 账户保存后会重算事项 |
| 资格判断 | 🟡 | 事项显示 relevance | profile + case facts 输入三值 AST | SQLite | `evaluate_case`; `rules.py` | 真实逻辑存在，但规则抽取和 scope 选择有限 |
| 本机画像用于 Demo | ⚪ | 页面可保存 | Case store 仍使用硬编码 profile | localStorage 写入 | `Page.vue`; `cases.ts` | 编辑后不会改变 Demo 判定 |
| 资料完整度 | ❌ | 无 | 无所需字段集/完整度计算 | 无 | 无代码 | MISSING |
| 事项内补充事实 | 🔵 | questions 页占位 | `PUT /cases/{id}/facts` 存在 | SQLite facts | `fact`; router | API 未被前端调用 |

### G. 用户与账户

| 功能 | 状态 | 前端 | 后端/API | 持久化 | 证据文件 | 备注 |
|---|---|---|---|---|---|---|
| 注册 | 🟡 | 邮箱+密码 | Argon2 hash，验证 token | SQLite | `account.ts`; `auth.py` | 无用户协议确认/限流/SMTP |
| 邮箱验证 | 🟡 | token 输入 | 15 分钟一次 token | SQLite | `auth.py:verification/consume` | 生产不返 token，但没有邮件发送 |
| 登录 | 🟡 | 已连通 | access 15 分钟 + refresh 长会话 | SQLite sessions | `api.ts`; `auth.py:login` | 会话仅内存，刷新后表现为退出 |
| token 自动刷新 | 🟡 | 401 时调 refresh | family 旋转 | SQLite | `api.ts:renew`; `auth.py:refresh` | 安全模型存在重要问题，见第 9 节 |
| 登出 | 🟡 | 我的页按钮 | 撤销所提交 refresh token | SQLite | `account.logout`; `auth.logout` | 断网时 `await auth.logout()` 抛错，前端后续跳转可能不执行 |
| 当前用户 | 🟡 | Pinia 内有 id/email | 登录响应返回 | 不本地持久 | `account.ts` | 无 `/me` API，无启动恢复 |
| 密码重置 | 🟡 | 表单存在 | reset token + 撤销所有 session | SQLite | `auth.py`; tests | 生产邮件链路缺失 |
| 修改密码 | ❌ | 无 | 无已登录 change-password API | 无 | endpoint index | 只能走忘记密码 |
| 登录设备/多会话 | 🟡 | 列表页 | `GET /sessions` | SQLite | `loadDevices`; `auth.sessions` | access token 也存在 sessions 中，列表可出现“access”会话；last_used_at 不更新 |
| 按设备撤销 | ❌ | 无 | 无 DELETE/revoke session API | 无 | endpoint index | MISSING |
| 隐私保护 / 安全分享 | 🟡 | `/privacy` 可处理粘贴文字、TXT 或 Case Evidence | 无对应 API；浏览器本地规则 | 不持久化 | `SafeShareView.vue`; `privacy.ts` | 可靠遮盖范围有限；邮箱/疑似学号只提示，不能声称已安全脱敏 |
| 隐私设置 | 🔵 | 菜单+路由和真实未接入状态 | 无设置 API | 无 | `/settings/privacy` | 本地隐私检测不等于账户隐私设置 |
| 账户设置 | ❌ | 无 | 无 | 无 | 无路由/代码 | MISSING |
| 数据清除/账户删除/导出 | ❌ | 无 | 无 | 无 | endpoint index; `docs/已知限制.md` | MISSING |
| owner 数据隔离 | 🟡 | 账户 store 分流 | 主要查询按 `owner_id` | SQLite | `owned`; API tests | 核心查询有隔离，但仍有完整性/授权边界问题，见第 9 节 |

### H. 首页统计与列表所需数据

| 指标 | 状态 | 当前数据是否足够 | 缺口 |
|---|---|---|---|
| 全部事项数量 | 🟡 | 客户端对 `GET /cases` 结果取 length；Cases“全部”Tab 已显示 | 工作台没有数量统计；大数据量需服务端 count |
| 进行中事项 | ❌ | 不足 | Case status 无正式迁移，也没有从 task 派生业务状态 |
| 即将截止 | 🟡 | 部分足够 | 有 deadline 但格式不统一，无时区/临近窗口定义/查询 |
| 已完成事项 | ❌ | 不足 | 没有完成 Case 的业务规则或可更新状态 |
| 最近事项 | ✅ | 足够 | API 已按 `updated_at DESC`，工作台取前 4 |
| 剩余天数 | 🟡 | 部分足够 | 需日期规范化、时区、date-only 边界和计算层 |
| 子任务数量 | 🟡 | resources 或 plan 可计算 | 列表 API 不返 task count，会造成 N+1 |
| 完成进度 | 🟡 | task status 可派生 | 未定义 skipped 是否计入，列表 API 不返聚合数 |

### I. Demo / Mock / 硬编码

| 位置 | 状态 | 事实 |
|---|---|---|
| `shared/demo/assessment_2024/*` | ⚪ | 固定“综合测评”模拟/脱敏通知、Blocks、两条规则、5 个任务和两份画像 |
| `mobile/public/demo/*` | ⚪ | 上述 Demo 的手工副本，前端直接 fetch；不是从 shared 运行时共享 |
| `mobile/src/services/demo.ts` | ⚪ | 用固定 `rules[0]` 当 scope、`rules[1]` 当 bonus，不是通用多事项仓库 |
| `mobile/src/stores/cases.ts` | ⚪ | 未登录始终显示一条 `demo-assessment`；求值画像硬编码为 2024 级本科生 |
| `shared/demo/scenarios.v2.json` | ⚪ | 只是 8 条场景目录/参数，除 assessment 外没有完整来源、材料和 DAG bundle |
| `/api/v1/demo/notices/assessment` | ⚪ | 后端公开 Demo 接口，用固定 profile 求值 |
| `_local_candidates` | 🟡 | 是真实生产回退，但只识别 4 类规则、6 个材料词，并硬编码两个通用步骤 |
| 新手教程 | 🟡 | `HomeView.vue` 内 3 步引导文案，仅用 localStorage 记完成 |
| `stores/app.ts` | 🔵 | 遗留 store，写 `zhishi-profile/zhishi-tasks`，但当前没有生产调用方 |
| 历史测试中的 FakeProvider | ⚪ | 只在 `server/tests/test_ai.py` 中用来验证 LLM 成功/回退链路 |

## 6. 核心数据链路追踪

### 流程 1：导入通知 → 最终生成事项

#### 1A. 文本

1. `ImportView` 在本地展示隐私预览；用户确认后，`importBatch` store 创建 Batch 并调用 `/sources/text`。
2. Source 保存文本摘要 metadata 和提取文本，状态为 `ready`；刷新后从 `/import-batches/{id}` 恢复。
3. 用户在来源页显式调用 analyze；后端为成功来源建立 Evidence，再复用 `analyze_case()` 和现有规则/LLM 校验链。
4. 同一 revision 重复 analyze 返回同一 Case，GET 只投影时间状态，不推进数据库。

结论：✅ 文本可以与 URL、文件在同一个 Batch 中生成一个可追溯事项。

#### 1B. 文件

1. `ImportView:chooseFiles()` 预检扩展名、数量和大小；确认后向 Batch files Source 端点发送 multipart。
2. 后端逐个读入 bytes，校验 10 文件/20MB/MIME，并复用 `parse_bytes()`。
3. `parse_bytes()` 按 MIME 解析或 OCR。
4. 每个文件独立保存 metadata、提取文本、状态和错误；analyze 将成功文件与其他来源合并为一个 Case。
5. 失败文件保留在来源列表并形成 `partial_failure`，不阻止成功来源生成结果。

结论：✅ 多文件可聚合为同一事项；当前只保存 metadata 与提取文本，不保存原文件内容。

#### 1C. URL

1. consent 后 Batch URL Source 调用 `fetch_public()` 检查 scheme/host/IP/每次跳转，限 10MB。
2. 正文先持久化为 Source 提取文本；analyze 时与同批次来源一起建立 Evidence。
3. 抓取或解析失败会保留 `failed` Source 和明确 error，供 partial failure 展示或删除后重试。
4. HTML 附件候选的独立选择与导入仍可后续扩展。

### 流程 2：事项 → 执行计划 → 完成步骤

1. 任务来源：`_local_candidates()` 或 `LLMProvider.analyze()`。
2. `_persist_analysis()` 将任务写入 `tasks`，并把相邻任务串行写入 `task_edges`。
3. `GET /api/v1/cases/{id}/plan` 读 tasks/edges，用 Kahn 算法拓扑排序。
4. `cases.ts:loadPlan()` 取回 `ordered_tasks`，`PlanView` 通过 `TaskTimeline` 按拓扑序渲染。
5. 用户从 Timeline 的状态操作选择新状态，`cases.ts:setTask()` 调 `PATCH /api/v1/tasks/{task_id}`。
6. `patch_task()` 校验状态枚举并更新 SQLite `tasks.status/updated_at`。
7. 撤销完成是把 `done` 再 PATCH 回 `todo/in_progress`，代码允许。

结论：账户模式的 `Case → Task DAG → status persistence` 是真实链路。但完成步骤不会推进 Case 状态，也不会计算当前步骤和整体进度。Demo 的任务修改刷新后不恢复。

### 流程 3：上传材料 → 保存 → 关联事项/步骤

1. `/vault` 只有路由和菜单入口。
2. 后端 `materials` 表只包含 `case_id,title,state,evidence_ids`。
3. `POST /cases/{id}/materials` 只新建“材料要求”，不接收文件。
4. 没有 material file/blob/object key、文件元数据、分类、有效期或用户库模型。
5. 没有 task-material 关联表。

❌ 链路在“用户上传材料”第一步中断。当前只有通知解析出的材料清单。

### 流程 4：登录 → 用户身份 → 按用户隔离

1. `POST /auth/login` 按 email 查 user，Argon2 验密码和 `verified_at`。
2. `issue()` 生成不透明 token，只将 HMAC hash 存入 `sessions`。
3. 登录同时创建 15 分钟 access session 和约 30 天 refresh session。
4. 前端 `setSession()` 只把两个 token 放内存。
5. 私有 API 依赖 `current_user()`，从 Bearer token 对应 session 取 user。
6. 主要业务查询用 `owner_id=user.id`，`owned()` 在读单资源时同时校验 id 和 owner。
7. 自动化测试覆盖 Case/resource/profile/sync 的跨账户隔离。

结论：🟡 owner-scoped 主链存在，但 token 类型没有分离：`current_user()` 接受任何未过期 session token，因此 refresh token 也可被当作 Bearer access token 访问业务 API；这是必须优先修正的安全边界。

## 7. 四个主页面的当前 UI 能力映射

### 7.1 工作台

| UI 元素 | 准备度 | 对应代码/数据 | 说明 |
|---|---|---|---|
| 导入并分析 | READY | `ImportView`、`ImportSourcesView`、`ImportProgressView`; ImportBatch APIs | 多来源持久化、状态恢复、部分失败与结果跳转已接通 |
| 最近事项 | READY | `GET /cases` 按 updated_at；`slice(0,4)` | 已在首页使用；未登录时实际是单条 Demo |
| 我的事项数量 | PARTIAL | `cases.items.length` 可派生 | Cases“全部”Tab 显示当前已加载数量；工作台未伪造数字，大数据量仍需服务端 count |
| 材料库 | MISSING | `/vault` 占位 | 无个人材料文件模型/API/UI |
| 使用指南 | READY | `HomeView` 3 步引导 | 可从工作台重复打开；完成标记只保存在 localStorage |
| 常见问题 | PARTIAL | `/help` 静态能力说明 | 已有常见问题内容；反馈提交和远端内容管理未实现 |

### 7.2 我的事项

| UI 元素 | 准备度 | 对应代码/数据 | 说明 |
|---|---|---|---|
| 全部 | READY | `GET /cases`; `cases.ts:load` | 列表可用 |
| 进行中 | MISSING | Case status 无迁移逻辑 | 不能用当前 `draft/review/demo` 可靠表达 |
| 即将截止 | PARTIAL | `cases.deadline` | 有部分日期，但缺归一化和筛选逻辑 |
| 已完成 | MISSING | 无 Case completion | task done 不会更新 Case |
| 分类 | PARTIAL | `cases.category` | 卡片可展示，没有筛选 API/UI；数据校验不一致 |
| 截止日期 | PARTIAL | `cases.deadline` | 可显示，覆盖率和语义不足 |
| 剩余天数 | MISSING | 当前 `CaseCard` 只显示原始 deadline | 需要日期归一化、时区与 date-only 语义后再计算 |
| 子任务数量 | PARTIAL | resources/plan 可取 tasks | 列表没有聚合字段，不应每卡单独请求 |
| 完成进度 | PARTIAL | task statuses 可派生 | 缺口径、聚合 API 和 UI |
| 搜索 | MISSING | 无 | 前后端均无 |
| 筛选/排序 | MISSING | 无 | API 固定 updated_at DESC |

### 7.3 执行计划

| UI 元素 | 准备度 | 对应代码/数据 | 说明 |
|---|---|---|---|
| 当前事项 | READY | `PlanView` 当前事项卡 + `AppBottomSheet` | 可以切换 Case 并用 query 保留选择；不是跨事项聚合 |
| 截止日期 | PARTIAL | Case/task deadline | 可显示，不完整 |
| 剩余天数 | MISSING | 无 | 同上 |
| Timeline | READY | `TaskTimeline` + DAG 拓扑序 | 当前按真实顺序展示；尚未可视化复杂分支边 |
| 已完成步骤 | READY | `tasks.status='done'` | 可真实读写，只需新 UI 分组 |
| 当前步骤 | MISSING | 无可执行性/前置完成派生逻辑 | 不可只把第一个 todo 当真实当前步骤，需定义 skipped/依赖规则 |
| 待完成步骤 | READY | todo/in_progress 状态 | 基础数据可用 |
| 预计耗时 | MISSING | Task 无 duration | 需 schema/API |
| 需要材料 | MISSING | 无 task-material relation | 不可从 Case materials 随意分配给步骤 |
| 相关文件 | MISSING | 原件不保存，无 task-file relation | 只有 evidence text，不是文件 |

### 7.4 我的

| UI 元素 | 准备度 | 对应代码/数据 | 说明 |
|---|---|---|---|
| 用户信息 | PARTIAL | login response 只有 id/email | 无昵称、头像、用户资料 API；会话不恢复 |
| 资料完整度 | MISSING | 无 | 需基于业务所需画像字段定义 |
| 个人画像 | PARTIAL | profile form + GET/PUT API | 真实账户模式可用；本机模式与 Demo 求值断开 |
| 材料库 | MISSING | `/vault` 占位 | 无底层功能 |
| 隐私保护 | PARTIAL | `/privacy` + `privacy.ts` | 本地文字/TXT/Evidence 检测可用，范围有限且不持久化；不是账户隐私设置 |
| 隐私设置 | MISSING | `/settings/privacy` 占位 | 同步范围、保留期限、导出和清除均未实现 |
| 登录设备 | PARTIAL | sessions list | 可列出，不能撤销单设备，且会话类型混杂 |
| 账户设置 | MISSING | 无 | 无修改邮箱/密码/删除账户/数据导出 |
| 帮助与反馈 | PARTIAL | `/help` | 使用说明与常见问题存在；反馈提交未实现 |
| 关于知事 | PARTIAL | `/about` | 有版本与数据原则；完整隐私政策、许可清单和远端版本信息未实现 |

## 8. API 与数据库覆盖概览

### 8.1 已有 API 组

- 认证：注册、验证、登录、刷新、重置密码、会话列表、登出。
- Demo：固定 assessment bundle 和简化 scenario catalog。
- 画像：GET/PUT 账户级 facts。
- 事项：创建、列表、详情、resources、Case facts、重算。
- 任务/材料/DAG：新建 task/material/edge，更新 task status，取 plan。
- 导出：TXT 和 ICS API；前端没有调用。
- 导入：文本、URL、文件，查进度、取消、重试。
- 同步：通用 push/pull 变更日志。

### 8.2 存在后端 API 但前端未接入

- `PUT /cases/{id}/facts`、`GET /cases/{id}/evaluate`。
- `POST /cases/{id}/tasks`、`POST /materials`、`POST /edges`。
- `GET /cases/{id}/export.txt`、`GET /cases/{id}/export.ics`。
- `/api/v2/sync/push`、`/api/v2/sync/pull`。
- `/api/v1/demo/scenarios`。

### 8.3 没有正式 migration

表由 `auth.py:init()` 和 `main.py:database()` 启动时幂等创建。没有 schema version、ALTER 升级、Alembic 或回滚脚本。因此对已存在数据库添字段时，`CREATE TABLE IF NOT EXISTS` 不会完成迁移。

## 9. 代码与安全审计发现

### 9.1 高优先级

1. **Access/refresh token 没有类型隔离。** `sessions` 无 token type，`current_user()` 接受所有未撤销 token，所以 refresh token 可直接作 Bearer token 调私有 API；`/refresh` 同样可接受 access token。建议增加 token purpose/type 并分开校验。
2. **会话无安全持久化与恢复。** 前端仅放内存，没有原生 Keychain/Keystore 适配；刷新丢失账户状态。
3. **异步任务是表面实现。** import 请求内同步解析/OCR/LLM，而 job 被直接标 completed；`retry` 生成 queued job 后永远无 worker 处理；`cancel` 无法取消正在执行的同步请求。
4. **材料库与原始文件存储缺失。** 新 UI 若展示文件、预览、分类、复用或与步骤关联，都没有数据基础。
5. **缺少版本化迁移。** 直接修改 DDL 无法安全升级旧用户数据库。

### 9.2 数据完整性与授权边界

1. `create_task()`/`material()` 要求 evidence id 非空，但不验证 evidence 是否存在、是否属于当前用户和 Case。
2. `edge()` 验证两个 task 属于当前 owner，但不验证它们属于 URL 中的 `case_id`；可写入跨 Case 边，并使 `plan()` 的 indegree 计算异常。
3. `FactIn.key` 只限制 `profile.*` 格式，没有使用 `PROFILE_FIELDS`；`scope` 也未校验。
4. Case facts 允许同 key 重复插入，`evaluate_case()` 查询无明确排序，重复时哪个值覆盖不是稳定合同。
5. 主要业务表多数未声明 Case/User/Evidence/Task 外键或 unique/check constraint，孤儿数据和非法枚举主要靠应用代码防止。
6. 文件导入的 import 状态 UPDATE 不带 `owner_id`（id 为随机 UUID，实际猜中概率低，但仍与全局 owner-scope 约束不一致）。

### 9.3 导入、解析和隐私

1. 文件 MIME 主要来自客户 `content_type`，没有 magic-byte 校验。
2. 20MB 限制只针对压缩前 raw bytes；DOCX/XLSX/PDF 没有解压比、页数、工作表数、像素数和解析时间预算，存在资源耗尽风险。
3. URL 抓取先 `safe_host()` DNS 解析再由 httpx 重新连接，没有锁定已验证 IP，需进一步处理 DNS rebinding/TOCTOU。
4. HTML 直接 `get_text()`，没有显式移除 script/style，也不保留表格/链接语义。
5. 导入确认页只对粘贴文本展示真实脱敏预览；文件/图片/URL 在前端未解析，用户看不到原件中什么会被发给后端。全局 `/privacy` 额外支持本机读取 TXT，但不改变上传链限制。
6. 服务端发给 LLM 前会脱敏身份证/手机/银行卡，但不脱敏邮箱、学号、姓名、地址等；前端对邮箱/疑似学号仅“标记类型”而不替换。
7. 文件解析异常可发生在 Case/evidence 已提交之后，然后 import 被标 failed，可留下无法从 import 反查的部分 Case 数据。
8. Android `clearPending()` 只删 SharedPreferences queue，不删 `filesDir/shared_*`，长期分享会累积私有文件。

### 9.4 业务逻辑与前端连通性

1. AI 返回的 `title/category` 未应用到 Case；文件 Case category 始终 `other`。
2. `evaluate_case()` 用“第一条规则”作为 relevance，模型没有 scope/eligibility 角色字段，规则顺序变化可改变事项判定语义。
3. 本地回退生成的两个任务是通用文案，不一定由原文直接支持；它们却关联全部 evidence blocks，证据粒度较粗。
4. profile 页本机保存与 `cases.ts` Demo 求值使用的硬编码 profile 断开；UI 文案“只用于规则判断”对 Demo 并不成立。
5. Demo 任务状态写入 `zhishi-demo-tasks`，但不读回；遗留 `app.ts` 另用 `zhishi-tasks`，键也不一致。
6. 路由无 auth guard，匿名用户仍可打开导入/手动创建表单；当前 UI 会阻止提交并提示登录，API 也会校验 401，但没有统一的登录重定向和 return-to 流程。
7. Auth、画像和若干旧工具页仍共用 `Page.vue`；在这些路由间复用同一组件实例时，部分表单 ref 可能保留上一次输入/消息。新拆分的主页面和产品页不受此项影响。
8. PWA Service Worker 采用 cache-first 且缓存版本固定，没有 activate 清理旧 cache 或 navigation fallback 策略；部署在非根路径时也可失效。
9. 前端依赖中 `axios`、`@capacitor/preferences`、`@ionic/vue-router` 当前未被生产代码使用；依赖范围均用 caret，实际重现依赖 lockfile。
10. 用户本机 `npm install` 输出报告 7 个漏洞（3 moderate、2 high、2 critical）及 tar/glob 弃用警告。本轮按要求未运行 `npm audit`，因此无法在不获取 audit 详情的情况下确认漏洞是生产路径还是开发工具链。不应盲目执行 `npm audit fix --force`。

### 9.5 测试覆盖缺口

2026-09-22 复验结果：

- `mobile`: `npm test` 通过，3 个测试文件、10 个测试全部通过。
- `mobile`: `npm run build` 通过，TypeScript 检查与 Vite production build 成功。
- `server`: `.venv\\Scripts\\python.exe -m pytest` 通过，21 个测试全部通过；有 5 条现有 deprecation warning，主要来自 FastAPI/Starlette lifespan 与 TestClient 依赖。

仓库测试覆盖了规则三值语义、文本/DOCX/XLSX 解析、空白图片 OCR 路径、核心账户流、owner 隔离、文本/URL 导入、本地 DAG/材料、AI 校验/回退和同步日志。明显未覆盖：

- PDF、JPG、XLS、HTML 的真实解析回归，扫描 PDF OCR，超大/损坏/压缩炸弹文件。
- 文件 API 的类型/大小/多文件/部分失败。
- task status PATCH、edge 防环、跨 Case edge/evidence 授权。
- job retry/cancel 真实执行（当前也无 worker 可测）。
- Android 分享队列桥的 JVM/仪器测试与私有文件清理。
- iOS/HarmonyOS 构建和真机链路。
- Vue 页面/路由/store 组件测试。当前前端测试只覆盖 API 连接文案、脱敏和规则引擎。
- 日期抽取、分类、标题、前端会话刷新与断网登出。

## 10. 文档与当前仓库的不一致

1. `README.md`、`docs/测试报告.md`、`docs/三端验收矩阵.md` 记录过 APK 已生成，但当前 `deliverables/` 中没有 APK。
2. `docs/platform-adaptation.md` 表述 iOS Share Extension 源码，这点属实；但 Xcode project 只有 App target，不能声称 iOS 分享端到端完成。
3. `docs/system-design.md` 说“移动端本地画像与事项缓存”，但当前没有本场事项数据库/IndexedDB/repository；只有 Demo JSON 和少量 localStorage。
4. 完整 v2 规格中描述的 PostgreSQL、SQLAlchemy/Alembic、worker、材料库、提醒、冲突复核、完整同步、数据删除/导出是目标架构，不是当前实现。
5. `docs/API.md` 列出的端点基本与代码一致，但没有表达 retry 无 worker、sync 与业务表未接通这两个重要限制。

## 11. Pre-UI Implementation Backlog

以下顺序按“数据模型 → 持久化 → Service/API → 业务逻辑 → 页面”依赖组织，不按视觉页面分组。

### P0：安全与数据基线

| 功能名称 | 为什么需要 | 当前缺什么 | 建议修改模块 | DB/schema | API | 数据迁移 | 关联页面 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| Access/refresh token 类型隔离 | 防止长期 refresh token 被当 access token | session purpose/type、专用校验 | `auth.py`, `api.ts`, account store | 是 | 是 | 是：旧 session 需撤销/升级 | 登录、设备、全部私有页 | M |
| 版本化数据库迁移 | 后续增字段/关系不能靠 CREATE IF NOT EXISTS | migration version/tooling/回滚路径 | `server` DB 初始化，新 migration 目录 | 是 | 否 | 是 | 所有 | L |
| 域模型约束和外键 | 防止跨 Case edge/evidence、孤儿数据和非法状态 | FK/unique/check 和应用校验 | `main.py` 当前 DDL/SQL，未来 repository | 是 | 部分 | 是 | 事项、计划、材料 | M |
| 安全会话恢复 | 用户不应每次启动重登 | Keychain/Keystore 适配、bootstrap/me | `api.ts`, `account.ts`, Android/iOS native port | 否 | 可能需 `/me` | 否 | 全局启动、我的 | M |

### P1：事项与日期模型

| 功能名称 | 为什么需要 | 当前缺什么 | 建议修改模块 | DB/schema | API | 数据迁移 | 关联页面 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| Case 状态机 | 支撑进行中/完成/归档/回收站 | 状态迁移、完成规则、PATCH API | Case model/repository/routes | 是 | 是 | 是 | 工作台、事项、计划 | M |
| 规范化日期/时间 | 剩余天数、逾期、即将截止必须有可计算语义 | date-only/timezone/precision/source/evidence | Case/Task schema，parser/date utility | 是 | 是 | 是 | 事项、计划、工作台 | L |
| Case 编辑与删除 | 手动纠正解析结果、管理事项 | PATCH/delete/archive API 与审计 | Case service/routes/store | 是 | 是 | 是 | 事项详情/列表 | M |
| 列表聚合 DTO | 避免新 UI 为任务数/进度做 N+1 | task_count/done_count/progress/normalized deadline | cases query/service | 可选 | 是 | 否 | 工作台、我的事项 | M |
| 搜索筛选排序 | 新事项页的核心能力 | query contract/indexes/UI state | cases API/store | 可能索引 | 是 | 否/索引迁移 | 我的事项 | M |

### P2：任务与 RuleFlow 模型

| 功能名称 | 为什么需要 | 当前缺什么 | 建议修改模块 | DB/schema | API | 数据迁移 | 关联页面 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| Task 执行元数据 | Timeline 需要耗时、建议开始日、硬/软截止 | duration、deadline semantics、notes/location/contact | Task schema/service | 是 | 是 | 是 | 执行计划/任务详情 | L |
| 当前可执行步骤派生 | 不能把第一个 todo 简化为当前步骤 | 前置状态、skipped/cancelled 语义 | plan service/API | 可能 | 是 | 可能 | 执行计划 | M |
| 任务 CRUD 与状态活动记录 | 用户需纠正步骤并可追溯 | UI 无增删改，无 status history | task routes/store/schema | 是 | 是 | 是 | 执行计划 | M |
| 跨事项计划聚合 | 底部“执行计划”应是任务中心 | 跨 Case task query、日期排序、冲突 | plan service/API/store | 可能 | 是 | 否 | 执行计划 | L |
| task-material/file 关联 | 支撑每个步骤的所需材料/相关文件 | relation model | Task/Material schema/service | 是 | 是 | 是 | 执行计划、材料 | M |

### P3：材料库与文件存储

| 功能名称 | 为什么需要 | 当前缺什么 | 建议修改模块 | DB/schema | API | 数据迁移 | 关联页面 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| 区分“材料要求”与“个人材料文件” | 避免 UI/数据语义混淆 | VaultItem/FileAsset 模型 | shared schema + server models | 是 | 是 | 是 | 材料库、Case 材料 | L |
| 私有文件存储与生命周期 | 上传/预览/删除/多端需真实文件 | local/object storage、hash、owner、retention | storage service + DB | 是 | 是 | 是 | 材料库、相关文件 | L |
| 材料 CRUD/分类/搜索/有效期 | 新 UI 直接依赖 | API/query/indexes | vault service/store | 是 | 是 | 是 | 材料库、我的 | L |
| Android pending 文件清理 | 避免私有目录无限增长 | 消费/取消/过期清理 | receiver/plugin/share service | 否 | 否 | 否 | 导入 | S |

### P4：导入与分析管线

| 功能名称 | 为什么需要 | 当前缺什么 | 建议修改模块 | DB/schema | API | 数据迁移 | 关联页面 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| 真实持久化 worker | OCR/LLM 不应占住 HTTP，retry/cancel 必须可执行 | 队列、租约、心跳、stage 幂等 | analysis job/worker/repository | 是 | 是 | 是 | 导入进度 | L |
| Import–Case–Source 模型 | 支持多来源合并、覆盖率、部分失败 | import_id/case_id/source/document version 关系 | schema + import service | 是 | 是 | 是 | 导入、来源、Case 详情 | L |
| 来源预览与结果确认 | 让用户控制上传和纠正结果 | sources/review API 与状态机 | import routes/store/pages | 是 | 是 | 是 | `/imports/:id/sources`、`/imports/:id/review` | L |
| URL 附件选择导入 | 当前只发现不处理 | attachment candidate 持久化/确认 API | import service | 是 | 是 | 是 | 导入来源 | M |
| 解析资源限制与文件真实类型检测 | 防止压缩炸弹/资源耗尽 | page/pixel/zip/timeout/magic 限制 | `parsing.py`, upload service | 否 | 否 | 否 | 导入 | M |
| 结构化字段扩展 | 地点、人员、优先级、多日期不能仅存正文 | schema + parser/LLM contract + evidence | shared/server models | 是 | 是 | 是 | 事项、计划 | L |
| 规则角色与评估版本 | 不能再用第一条规则当 relevance | scope/eligibility 标识、fact/rule snapshot | Rule/Evaluation schema/service | 是 | 是 | 是 | 规则、事项概览 | L |

### P5：同步、平台与账户完整性

| 功能名称 | 为什么需要 | 当前缺什么 | 建议修改模块 | DB/schema | API | 数据迁移 | 关联页面 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| 业务变更与 sync 接通 | 当前 sync 日志不会改变 Case/Task | repository/outbox/apply/pull merge | mobile repository + server sync | 是 | 是 | 是 | 同步状态、全部数据页 | L |
| 本机模式的真实仓库 | 未登录不应只有固定 Demo | IndexedDB/原生 SQLite、repository 抽象 | frontend repositories/stores | 是（本地） | 否 | 是：localStorage | 所有 | L |
| 个人画像与 Demo/本机求值接通 | 修复“保存了但不影响结果” | 统一 profile source | cases/app stores + demo service | 否 | 否 | 可能 localStorage 键合并 | 画像、Demo | S |
| 设备会话管理 | 用户需识别并撤销设备 | refresh-only device session、last_used_at、revoke | auth DB/API/UI | 是 | 是 | 是 | 登录设备 | M |
| SMTP 验证/重置 | 生产注册否则无法完成 | mail provider/template/rate limit | auth/mail service | 可能 | 是 | 否 | 注册、找回密码 | M |
| 账户数据导出/清除/删除 | 隐私闭环和上线必需 | API、文件生命周期、tombstone | account/privacy service | 是 | 是 | 是 | 隐私、账户设置 | L |
| iOS 分享真正接入 | 当前只有未绑 target 源码 | target/app group/main-app bridge/field contract | Xcode project + Swift plugin + `share.ts` | 否 | 否 | 否 | 导入 | M |
| HarmonyOS 主链 | 当前只是原生基线 | Want/file picker/API/repository/pages | `harmony/` | 是（本地） | 是 | 是 | 三端所有页 | L |

### P6：最后才进行的 UI 接入

完成 P0–P5 中与目标页面相关的数据和 API 合同后，再重构 Vue 页面。界面层应至少拆分为独立路由页、领域 store/repository、可复用事项卡、任务 Timeline、日期/进度派生器和明确的 loading/empty/error/offline 状态。这一阶段不应用写死数字或 Demo 充当未实现统计。

## 12. 建议下一轮的 5 个优先项

1. 修正 access/refresh token 类型隔离，建立可迁移的 DB 基线和关系约束。
2. 完整化 Case 状态、日期语义、编辑/完成/归档和列表聚合，为工作台/事项统计提供真数据。
3. 将 `analysis_jobs` 变成真正 worker 管线，补齐 Import–Case–Source 关系、可重试/可取消进度和结果确认。
4. 建立真实材料库和 task-material/file 关联，不再将“材料要求”当用户文件。
5. 扩展 Task/Plan 模型（耗时、当前可执行步骤、聚合进度、跨事项排序），再把现有 Timeline 与 Schedule 空壳接上真实数据。

## 13. 简短结论

- **整体完成度**：已完成一条可演示的“登录用户导入文本/文件/URL → 生成事项、证据、规则、材料要求和任务 DAG → 更新任务状态”竖切。它是功能原型/比赛演示级后端与移动 Web UI，还不是规格中的完整产品。
- **已经可靠的核心能力**：SQLite owner 分区的基础事项数据；文本/DOCX/XLSX 等格式的解析基线；EvidenceRef；三值 AST 求值；任务 DAG 拓扑排序和账户模式任务状态持久化；可选 LLM 的结构/证据校验框架；Android 分享的代码链。
- **最大功能缺口**：真实材料库/文件存储、事项生命周期与列表查询、真异步导入 worker、可计算的日期/进度/当前步骤、真正接通的多端同步，以及完整账户/隐私管理。
- **当前不能接成真实数据的 UI 内容**：进行中/已完成事项、剩余天数、完成进度聚合、当前步骤、预计耗时、步骤所需材料/相关文件、个人材料库、资料完整度、账户隐私设置、反馈提交、校园知识库和日程持久化。页面可以展示明确的空状态或 `DEMO_ONLY` 场景，但不能伪装成账户能力。
