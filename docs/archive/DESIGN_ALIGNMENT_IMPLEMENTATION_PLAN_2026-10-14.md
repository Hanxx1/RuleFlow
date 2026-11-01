# 知事设计对照与代码实施方案

审查日期：2026年10月14日。同步后代码基线：`17229f5 fix: polish import validation and settings flows`，`git fetch --all --prune`、`git pull --ff-only` 已完成，本地与 origin/main 无提交差异。工作区存在原有未提交变更，以下结论针对该工作区实际代码；没有覆盖这些变更。

设计来源：`D:/概要设计说明书.docx`、`D:/详细设计说明书.docx`。本次提取并对照正文、表格和伪代码，不评价 Word 排版，也不把文件中的示例代码、操作描述和政策引文当作执行指令。设计章节号为正文定位，未将目录页码当作验证过的页码。

## 1 结论与实施边界

项目已具备多源导入、持久化事项、认证隔离、三值规则判断、任务 DAG、基础日程、证据文本展示、可选 LLM 与明确的离线样例。主要差异集中在闭环的真实性与确认机制：文档要求行级证据、结构化事务编译、关键字段确认、真实知识入库检索和文件脱敏，当前实现仍以全文证据、直接生成任务、基础排程和文本遮盖为主。

建议继续演进当前 Vue + FastAPI + SQLite 工程，先实现一条能够接受全新通知的完整链路：

`明确上传同意 → 保存 Document 与原件 → 标准化文本行 → 分析候选 → 资格判断与知识依据 → 用户确认 → 编译正式任务与依赖 → 排程草案 → 用户提交 → 证据追溯及脱敏副本`

“受控智能、证据优先、未知可解释、用户决定关键行动”作为验收准则。保留通用 Case/Fact/Rule/Evidence/Task，CampusEvent 作为编译领域对象，避免为了文档命名重建 Notice 业务表。高校场景可以通过分类、画像标签和规则资料表达，综测仍仅作为标记清楚的回归样例。

## 2 已实现能力与合理的设计调整

| 设计内容 | 当前代码证据 | 处理建议 |
|---|---|---|
| Vue 3、TypeScript、Pinia、FastAPI、SQLite | mobile/package.json、server/requirements.txt | 保留，符合轻量单体原则 |
| 用户画像、缺字段提示、硬条件三值计算 | server/app/main.py 的 evaluate_case、server/app/rules.py | 复用，补字段类型和规则契约一致性 |
| 结构化模型输出、限制 AST、证据引用校验 | server/app/ai.py 的 AIAnalysis、validate_candidates | 已有基础，增强字段级证据与日期语义 |
| 模型不可用时降级 | server/app/main.py 的 analyze_case | 当前明确返回 local/local_fallback，可继续保留；降级结果须进入待复核候选 |
| 所属用户隔离、安全密码与轮换会话 | server/app/auth.py、settings.py、tests/test_foundation.py | 保留，不重写认证；新资源继续强制 owner_id |
| DAG 环检测、基础时间冲突检测及日程 CRUD | main.py 的 edge、schedule endpoints；services/schedule.py | 属于部分完成，补确认门禁与草案一致性 |
| Android ContentResolver 分享接收 | mobile/android/app/src/main/java/com/zhishi/ruleflow/ShareReceiverActivity.java | 保留，不用真实路径假设替换；扩展实机验收 |
| Web 竞赛版与三端产品定位不同 | 概要§1.3；mobile/android、mobile/ios、harmony | Web 作为本轮共享闭环验收主入口，Android 跟随；三端是扩展，不是实现错误 |
| 文档指定 Element Plus/Tailwind、SQLAlchemy/Alembic | 实际使用自定义 Vue/CSS、sqlite3、自有 migration | 不能仅因库名不同认定功能缺失。本轮不为对齐名称迁移 UI 或 ORM |
| Case 替代 Notice | cases/facts/rules/evidence/tasks 表及 shared/schemas/case.v2.schema.json | 符合 AGENTS.md 通用模型约束，在文档补模型映射即可 |

## 3 实质差异与影响

| 编号及优先级 | 文档要求 | 实际实现及定位 | 具体影响 |
|---|---|---|---|
| A01 P0 | 概要§4.10、详细§8.4：关键字段确认后才进入执行及最终日程 | `_persist_analysis` 直接插入 todo 任务；schedule/items 校验 owner、关联和占用，没有字段确认门禁；AnalysisResultView 只有通用编辑及复核提示 | “待复核”仍可创建正式任务和安排时间；任意改 Case.status 不能代替有效确认 |
| A02 P0 | 详细§6.1、§6.4：多个日期区分语义，保留 raw、标准值、推断标记 | import_text、analyze_import_batch 用正则取第一个日期；TaskCandidate.deadline 只有字符串，validate_candidates 不验证 deadline 与短引的对应关系 | 发布日期/活动日期可能被当作截止日期；只有有效引用并不代表引用支持该时间 |
| A03 P0 | 详细§6.5、§8.3：受控编译，原文动作与建议动作分开，依赖引用 action_id | `_local_candidates` 对有文本的来源生成固定“核对”“准备并提交”步骤，并将所有证据附到每项；`_persist_analysis` 用 zip 相邻任务创建边 | 普通公告也可能生成提交任务；并行步骤被强行串行，缺少依赖依据 |
| A04 P0 | 概要§4.9、详细§5.4、§11.4：行级引用与原图/PDF 高亮 | parsing._ocr 返回 bbox/confidence，但 evidence 表不存坐标；批次把所有块拼成 extracted_text，再保存“批次来源全文”、page=null；原生 PDF 只提全文 | 现有 EvidenceBottomSheet 只能看文字与粗略位置，无法验证图像区域，也无法支持区域脱敏 |
| A05 P0 | 概要§4.8；AGENTS：上传前 Privacy Guard 与明确确认 | ImportView 对粘贴文字做本地预览，文件只有格式/体积检查；批次文件接口只有 consent 布尔值；Vault 上传接口没有同等确认契约 | 文件上传确认存在，但上传前隐私检查尚不完整；不能宣称图片端侧严格模式已完成 |
| A06 P1 | 概要§4.5、详细§7：实际资料入库、分块、检索、来源回答 | providers/knowledge.py：Demo 为 fixture_keyword，Real 为 UnavailableKnowledgeProvider；没有知识入库/search/ask 闭环 | 样例条款展示不能作为真实跨文档 RAG 完成凭据；未配置状态当前是如实返回 |
| A07 P1 | 详细§9：权重优先级、偏好、每日限额、缓冲、拆分、周期课与锁定重排 | schedule.py 已拓扑排序和占用避让，但以 deadline 排序，固定 08:00–21:00、30 分钟取整，不拆分；PlanSchedule 逐条 POST 日程，没有 draft/commit | 基础排程可用，但不符合完整算法；后置任务可以先单独提交，整体草案的一致性无法保证 |
| A08 P1 | 详细§10：用户选择 finding、图片/PDF永久脱敏副本、风险评分 | privacy.py 只支持身份证/手机号/银行卡文本规则；SafeShareView 只接 TXT/粘贴文本并全部遮盖 | 未实现坐标融合、用户逐项选择、风险评分、二维码检测或图片/PDF输出 |
| A09 P1 | 详细§11.4、§13.3：真实处理阶段、保留中间结果、可重试 | analyze_import_batch 完成分析后写未来时间点，GET 再投影 queued/processing；这段逻辑未按 Demo 模式限制；旧 retry 仅创建 queued job，没有消费实现 | 进度提示不代表实际步骤；“重试已排队”不等于能重新分析 |
| A10 P1 | 详细§6.3、§6.4：完整分析快照、最终确认值、版本 | analysis_metadata 只有模式、摘要、问题、版本等，缺完整 analysis_json/final_value；用户改 deadline 会设置 user_input 且清空引用 | 无法还原每次提取候选和用户修正；按 AGENTS 严格要求，空引用应“待核对”，用户录入也应建立来源记录 |
| A11 P1 | 详细§4：兴趣与时间偏好，资格和相关程度区分 | Fact/ProfileIn 为通用字典；主要结论 TRUE/FALSE/UNKNOWN；AI 与两端引擎各自维护规则限制 | 硬资格已有基础，但缺软相关性；schema field 目前是通配 pattern，不是文档预期的明确画像清单；前端类型不匹配比较可能返回 FALSE，后端返回 UNKNOWN |
| A12 P2 | 详细§2.3、§12、§14：服务分层、统一错误、集中配置 | main.py 集中 DTO、路由、SQL和流程；现有 envelope 是 data/request_id/meta，错误混用字符串 detail 与对象；ai/auth 各自 getenv | 业务可运行，但新增确认/RAG/脱敏会继续扩大耦合；应增量抽服务并统一新错误契约 |

上述为静态调用链证据，不将历史 FEATURE_AUDIT/已知限制 的文字作为当前实现证明。旧限制文档中部分描述已过时，应在功能验收后重新生成状态矩阵。

## 4 数据与契约方案

### 4.1 保留现有业务表并增量迁移

审查基线 migration 为版本5；第一批已追加006 `analysis_review_gate`，优先堵住未确认执行。下表是目标模型，原拟版本号不再作为执行编号，后续按实际版本递增；每次迁移需验证旧数据与重复启动，不重置数据库。

| 迁移 | 新增结构 | 关键约束 |
|---|---|---|
| 006 文档与证据定位 | documents、document_lines；evidence 新增 document_id/line_id/quote/char_start/char_end；import_sources 关联 document_id | Document 有 owner_id、storage_key、hash、mime、页数、状态；Line 有稳定 id、page、text、bbox、coordinate_space、page_width/height、ocr_confidence；所有资源验证同 owner |
| 007 候选与确认 | analysis_runs、field_reviews、confirmation_events、audit_events；Case.analysis_revision；Task.analysis_run_id/action_id/origin/confirmation_status | 分析 run 保存不可变 JSON 快照、schema/prompt/parser 版本、源 hash、画像快照/版本；确认绑定 revision，旧候选确认不得覆盖新分析 |
| 008 草案与排程 | schedule_drafts、schedule_draft_allocations；schedule_items 增加 locked/version/segment_index；Task 增 splittable/importance | 每任务可有多个片段，不能沿用当前“同一 task 只能有一个日程”的校验；提交对整个草案事务性校验 |
| 009 知识资料 | knowledge_documents、knowledge_chunks、knowledge_index_jobs | chunk 有 owner/可见域、document/version、页码/行引用、类别/生效时间；索引不能绕过 owner 过滤 |
| 010 隐私副本 | privacy_scans、privacy_findings、document_derivatives、processing_consents | finding_id 关联 document revision 与原始坐标；持久化仅存所需定位信息/掩码预览，避免重复保存 raw_value；副本不覆盖原件 |

旧全文证据标记为 `locator_quality=block`，不能补造 bbox。旧任务标记为 `legacy_unreviewed`，继续可查看，但在新排程前要求确认；已有日程保留，后续变更时展示旧依据限制。Demo 的明确样例确认状态由 fixture version 管理，不能借用正式用户的数据。

### 4.2 统一字段候选

新增 `server/app/schemas/analysis.py`，定义 AnalysisCandidate/CampusEvent 与通用 EvidenceField。推荐结构示意，正式值均从证据或用户提交产生：

```json
{
  "value": null,
  "raw": null,
  "evidence_ids": [],
  "origin": "document",
  "verification_status": "needs_confirmation",
  "inferred": false,
  "confidence": null,
  "review_reasons": ["missing_evidence"]
}
```

deadline 额外记录 precision、timezone、semantic_role；日期精度与时间精度区分，原文只给日期时不展示为明确的 23:59 截止时刻。模型信心不是概率，不能为完整界面填固定百分数。

用户修正写成 `user_assertion` 来源的 Evidence，记录提交者、时间、最终值及可选原文关联，界面标“由你确认”，不得标为学校官方依据。只有用户点确认、后端校验通过才变为 confirmed。建议步骤引用其业务上下文，并明确标“建议，可删除”；缺依据的系统结论一律待核对。

Case.status 保留业务状态，另设 analysis/review 状态。Task 保留 todo/in_progress/done/skipped，不把 scheduled 混入完成状态；排程状态由实际片段计算。这样符合状态机理念，也避免破坏现有过滤、进度和移动端逻辑。

### 4.3 增量 API 合同

沿用 `/api/v1`、Case ID、现有 data/request_id/meta，避免为了路径与文档一致重复建设 Notice API。旧接口逐步委托服务，新响应加字段；统一错误为 `error: {code, message, details}`，前端兼容旧 detail，随后迁移。

| 新增或增强接口 | 行为 |
|---|---|
| GET /api/v1/documents/{id} 与 /content | 同 owner 文档/行/预览或文件内容；不接受客户端真实路径 |
| POST /api/v1/cases/{id}/reanalyze | 从保留 Document/Line 创建新 run；旧确认、任务、快照不被静默覆盖 |
| GET /api/v1/cases/{id}/reviews | 返回待核对字段、全部候选、原因、证据和 revision |
| POST /api/v1/cases/{id}/confirm | 提交 revision、所选日期/动作、修正值、明确确认；事务保存 final_value 与审计 |
| POST /api/v1/cases/{id}/compile | 只接 confirmed candidate IDs；幂等生成正式任务、材料关联和 DAG |
| POST /api/v1/schedule/preview | 保留现路径，返回 draft_id/version、segments、conflicts、basis_versions |
| POST /api/v1/schedule/commit | draft_id/version + 明确确认；重校验依据版本、deadline、依赖、占用并原子提交 |
| POST /api/v1/schedule/replan | 锁定片段和候选任务；生成新草案，不改正式日程 |
| POST /api/v1/knowledge/documents、/search、/ask | 资料入库、检索、基于引用回答；无依据不调用模型硬答 |
| POST /api/v1/documents/{id}/privacy/scan、/redact | 保存检测与用户选项，生成副本；仅接 finding_ids，不接任意 bbox/path |

所有 mutation 有同 owner、同 Case、revision、幂等键校验。旧 schedule/items 的 task 分支也走同一确认、截止时间、依赖和并发校验，不能只保护新 commit 接口。

## 5 代码实施工作包

### W1 先堵住错误自动执行与日期误用

修改 main.py 的 import_text、analyze_import_batch、_local_candidates、_persist_analysis；新增 services/date_candidates.py、services/review.py、schemas/analysis.py，实施迁移007的最小字段。

1. 去掉“首个日期直接写 deadline”。提取所有候选及局部上下文，分类 publish_time/event_time/submission_deadline/unknown；未明确“截止/提交前”等语义时返回待核对。
2. 缺年、日期冲突、时区不明、多个不同提交环节分别记录，不默认选择最早/最晚。用户确认前不写最终 deadline。
3. 分析只持久化候选和证据。先给旧任务补 confirmation_status，全部任务日程写入口执行门禁，以免重构过程中产生旁路。
4. 本地降级不再给任意文本补“准备并提交”。先要求原文动作+对应短引；无动作的通知只展示理解和待核对信息。
5. 用户在 AnalysisResultView 查看候选、证据、原因，再点“确认并生成行动步骤”。修改字段后原确认失效。

验收：通知含发布、活动、报名三个日期时只把明确报名截止列作候选；缺年标 inferred；直接绕过 UI 调 schedule/items 会得到 REVIEW_REQUIRED；模型超时与未配置仍保留本地可核查结果，Demo 可用。

### W2 补齐原件与行级证据

新增 services/documents.py、repositories/documents.py、schemas/documents.py；改 parsing.py 和导入来源服务；实施006。复用现有 VaultContentProvider 的安全存储思想，文档单独 namespace，不能因材料库删除误删通知证据。

1. 按流累计读取限制，检查扩展名/MIME/签名和真实可读性；按设计设置图片10MB、PDF20MB/20页，配置总像素/解析预算，避免先无限 f.read 再检查。
2. UUID 存原件及处理状态，解析失败也保留文档，可授权删除/重试。导入时经过 Privacy Guard 与有效确认。
3. 原生 PDF 用已有 PyMuPDF 获取行/字符位置，扫描页才 OCR；OCR 四点框规范为可表示多边形，记录渲染变换并还原到 PDF point。
4. DOCX 提取段落和表格（当前仅 paragraphs，会漏表格）；表格/文本用段落/单元格定位，不伪造 Word 页坐标。
5. 稳定 line id 为 document+revision+page+行号；保留 block: EvidenceRef ID，通过关联指向 line。批次聚合继续保留每来源和每行，不能回扁平全文。
6. 新增 EvidenceViewer.vue，图片/PDF 页预览+叠加高亮；移动端单栏与底部抽屉，Web 宽屏原文/结果双栏。文本证据降级到行高亮。

验收：同一句截止时间从分析到原图高亮的位置一致；不同 PDF 渲染尺度不漂移；跨文档 line 不混淆；缺 bbox 显示可读说明；伪装文件、空 OCR、超页数均有明确错误。

### W3 事务编译与资格规则

新增 services/compiler.py、services/relevance.py、schemas/campus_event.py；ai.py 改为候选协议，TaskService 只读确认后的 CampusEvent，不读原始模型 JSON。

1. 每 action 有稳定 action_id、origin、证据、选中状态、duration 与具体 submission。明确原文动作和建议动作，用户可修改/删除。
2. 删除按数组 zip 建依赖。接受引用现有 action_id 的依赖，验证前置语义、端点归属及环；只有被标为建议且用户接受的边可降级移除，硬依赖冲突返回 TASK_DEPENDENCY_CONFLICT。
3. 保存边来源/理由；任务材料按 action 关联，不把所有材料挂到最后一项。
4. 幂等编译用 `(owner_id, analysis_run_id, action_id)` 唯一约束。新分析不能删除用户已完成/手工编辑任务，返回差异供选择。
5. eligibility_truth 与 relevance_level 分开：硬冲突 FALSE；缺条件 UNKNOWN；软兴趣只排序，不能把 UNKNOWN 提升为 TRUE。
6. 统一 shared/rule_ast.schema.json 的字段策略，明确 allowlist 与类型；当前字段是通配 pattern，不能声称已枚举限制。以已用字段为迁移基线，将画像结构字段与参与 AST 的事实字段分开。
7. 后端/TS/ArkTS 对非法数值和缺失一致返回 UNKNOWN。Pydantic+shared schema 双层约束，模型不能添加操作符或执行任意代码。

验收：普通公告无凭空提交任务；并行准备不强制串行；虚构边/环/越权引用拒绝；综测、竞赛、奖学金、普通公告都能复用编译器；类型错误与缺排名在三端一致。

### W4 真实知识库和有来源的补全

扩展 providers/knowledge.py；新增 services/knowledge.py、schemas/knowledge.py、EmbeddingProvider/VectorIndex 接口，实施009；KnowledgeEvidenceView 加资料管理与查询入口。

1. 用 W2 的文档解析入库；按条款/标题分块，500–800字、80–120字重叠作为可调默认，保留来源版本/生效日期/学院/line refs。
2. 第一阶段允许 SQLite FTS5 作为精确条款检索基线，明确标 keyword 而非声称向量 RAG。启动探测 FTS5，缺失时显式 unavailable。
3. 接可替换 EmbeddingProvider 和本地持久化向量索引；竞赛小语料可先用已有 NumPy 做经 owner 过滤的精确余弦检索，达到需要的规模再评估 FAISS，避免首轮新增多个原生依赖。
4. 文本、chunk 元数据与索引一致，记录 embedding model/dimension/version；失败为 indexing_failed，可重建，不能丢原文或混维度。
5. 索引检索前后均 owner/visibility 过滤。通知引用“详见某细则”触发检索；候选证据补到分析 run 后仍执行验证和确认。
6. 来源只取本次召回 chunk；回答以可验证的 claim+citations 结构返回。无依据/来源失效返回 RAG_NO_EVIDENCE；索引未配置与无命中分开。

验收：导入一份全新的规则文档即可检索，不靠 fixture；owner A 查不到 B 的 chunk；模型虚构引用被拒；无资料不返回综测样例；删除文档会同步失效引用和索引。

### W5 可提交的确定性排程

扩展 services/schedule.py；新增 services/schedule_drafts.py、schemas/schedule.py；实施008；PlanSchedule 加耗时、拆分、偏好、锁定、草案批量确认。

1. 基于已确认的任务事实。优先级按设计 `0.40U+0.30I+0.15D+0.15P`，参数集中配置；deadline 与依赖是硬约束。
2. 展开周期课程，在规划窗口做区间差集；每天限额、偏好、buffer、最小片段显式记录。缺耗时先要求用户选值，算法默认值标注为建议。
3. 对可拆任务分段，依赖以所有片段完成时间判断；固定课程、忙碌和 locked 不移动。
4. preview 保存短期 draft，包括 task/Case/占用版本、分段与冲突。commit 在 SQLite 写事务里重新查占用、确认和依赖，全部通过才写入；冲突时整体拒绝，重预览。
5. 独立 task 日程 CRUD 也检查依赖与 deadline；用户选择只提交一部分时必须含未完成的前置闭包。删除日程后同步派生排程状态。
6. 冲突返回 required_minutes、available_minutes、reason、建议动作；拖动后做局部校验，锁定并可重排剩余任务。

验收：三段课程空隙可容纳一个允许拆分的任务；不可拆任务返回不足；提交过期草案拒绝；并发日程不重叠；后置不可先独立保存；缓冲与每日限额真正生效。

### W6 文件隐私检测与副本

扩展 privacy.py、SafeShareView；新增 services/redaction.py、schemas/privacy.py；实施010。复用已安装 Pillow/PyMuPDF，实现选项和真实文件输出，再补二维码/语义。

1. Regex 补邮箱、带上下文的学号及校验；不把所有8–12位数字认定学号。身份证/银行卡格式和校验区分，不能给启发式结果虚构概率。
2. Finding 关联 W2 坐标。风险分按文档公式配置，confidence 无校准时用明确的启发式标签，内部评分不显示为“泄露概率”。重叠 finding 合并。
3. 用户选 finding_ids；服务从同 owner、同 document revision 的可信 bbox 生成图片遮挡或 PDF 永久 redaction。无定位时返回 REDACT_LOCATION_MISSING，不给仅画遮罩的 PDF 当永久脱敏文件。
4. 新文件保留原件，图片清理 EXIF，PDF检查文本层、图片与元数据是否残留选中敏感项。提供副本预览、下载和系统分享。
5. 普通账户保存与远程模型处理分别提示范围；外部检测/Embedding/LLM 只处理用户同意的范围。语义姓名/地址作为可选检测器，不为隐私扫描先把原敏感内容无提示发远端。
6. 对无法在上传前本地扫描的格式，Privacy Guard 必须明确“未检查该格式”并给用户人工确认/本地预处理选择，不能展示“安全已检查”。端侧严格 OCR 单独列为后续能力。

验收：选中的手机号在下载图片或 PDF 中无法恢复；未选项保留；原件 hash 不变；错误响应与审计不含原始敏感实体；未授权 upload/model 请求拒绝；跨账户 finding_id 拒绝。

### W7 真实进度与工程收口

main.py 留启动/路由注册，逐步抽 api/imports.py、cases.py、schedule.py、knowledge.py、documents.py；repositories 用参数化 SQL，动态标识符仅来自服务端固定映射。避免一次改动整个单体。

小规模首版可同步处理并如实显示完成阶段，不引入虚假队列。需要异步时用持久化 job 加单进程受限执行器：写真实 stage/state、启动恢复未完成 job、重试真正消费、取消按阶段检查。多进程部署前再替换执行器，初版不把内存后台任务称为可靠队列。

时间投影只允许显式 Demo 演示，Real 停用。集中 Settings、错误枚举及脱敏审计；业务 GET 只读，例如当前 `/cases/{id}/evaluate` 会持久化计算结果，应改只读或 POST reevaluate。更新 API/能力矩阵/已知限制，以实际测试和产物为准。

## 6 实施顺序与停止条件

| 阶段 | 工作包与交付 | 通过门槛 |
|---|---|---|
| 第1阶段 | W1 + W2，候选确认门禁、Document/Line、原件与证据查看 | 新通知的所有关键输出可定位；未确认不能排程；日期不猜；Demo 回归通过 |
| 第2阶段 | W3 + W4，通用事务编译和真实规则资料 | 完全陌生的竞赛/奖学金通知可借导入细则生成可核查候选；硬资格不受软兴趣覆盖 |
| 第3阶段 | W5 + W6，确认计划和脱敏副本 | 截止前无冲突安排、过期草案拒绝、可拆任务、文件永久脱敏可验证 |
| 每阶段收口 | W7中与该功能有关的分层、错误、审计、进度 | 重试有效、阶段真实、跨账户测试、移动端主链路通过 |

每阶段拆成可评审小改动，先 schema/migration → service tests → API → UI/移动测试 → 更新文档。工期需要根据人员、是否已配置模型/Embedding与设备环境确认，不把表中阶段当作日历承诺。

首轮不新增独立 AI 聊天助手、不重写设计系统、不做自动邮件/报名提交、不把主验收押在鸿蒙/iOS签名环境。桌面和视频代码属于已有本地工作，不纳入本次业务改造的覆盖范围。

## 7 必须补的测试与验收样例

当前测试通过不代表文档完整实现。新增回归优先覆盖跨模块行为，不写只镜像函数实现的测试。

| 类别 | 至少覆盖 |
|---|---|
| 文档与解析 | DOCX表格、原生/扫描混合PDF、坐标换算、空OCR、损坏文件、扩展名/MIME不一致、超页数、owner授权 |
| 日期与证据 | 发布/活动/截止三日期、无年日期、多环节截止、模型虚构日期但引用存在、未知line/quote、源文件版本变化 |
| 确认与编译 | 未确认从任意API排程被拒、revision冲突、用户修正来源、幂等编译、建议可删除、DAG环、完成任务保留 |
| 规则 | UNKNOWN不变FALSE、错误字段类型、硬否决、缺排名提示、shared vectors在Python/TS/ArkTS一致 |
| 知识 | 全新资料入库与检索、无依据、模型引用不在召回、不同维度索引、删除/版本失效、两个owner隔离 |
| 排程 | 拆分/不可拆、每日限额、缓冲、课程周期、锁定重排、前置闭包、草案过期、并发冲突与事务回滚 |
| 隐私 | finding选择、坐标缺失、原件不变、PDF文本/图像残留、EXIF、跨owner、上传/模型分别确认、错误日志脱敏 |
| 移动交互 | 360/390px宽度，证据打开/关闭/滚动、确认字段、批量计划提交失败、文件预览、断网/超时、页面刷新与账户切换 |

以四个固定虚构样例作演示：竞赛完整链路、缺排名奖学金、跨文档综测、含姓名/手机号/学号/二维码截图。再加一个测试时临时生成的新通知与新细则，证明处理链不是展示预置结果。

## 8 首次只读审查的验证与交付事实

本次只新增本方案文件，没有修改生产代码、设计 Word 或原有未提交文件，没有构建新 APK，也没有提交 Git。

- 后端：`E:/DevTools/PythonPortable/python.exe -m pytest -q -p no:cacheprovider`，52项通过。首次使用默认 vault 目录时51通过、1项因 WinError 5 写权限失败；设置 `VAULT_UPLOAD_ROOT` 到临时测试目录后全量复验通过，无代码修改。
- 前端：`npm test`，6个测试文件19项通过；其中包含当前未提交的 demo.test.ts。
- 类型：`npm exec vue-tsc -- --noEmit` 通过。
- 未运行本轮浏览器/移动实机验收，未调用真实外部 LLM/Embedding，未验证 Word 图示或版式。上述端到端能力仍需按工作包验证。
- 当前已有 APK：`E:/ZhiShi/deliverables/Zhishi-RuleFlow-debug.apk`，9,901,220字节，文件时间2026年9月25日。它是历史调试产物，不证明与2026年10月14日当前源码一致；后续功能完成需重新构建并记录 commit、构建参数和 SHA-256。
- Harmony 为 ArkTS/ArkUI 工程基线；当前没有本轮 SDK/设备/签名验收。iOS没有本轮 macOS/Xcode/签名验收，不以源码存在代替IPA/HAP完成。

开发完成后更新 docs/architecture/API.md、docs/product/FRONTEND_CAPABILITY_MAP.md、docs/product/已知限制.md 与三端验收矩阵，把“代码存在”“Mock”“已接真实服务”“实机通过”分别记录。

## 9 第一批代码实施进展

按用户要求边实现边更新文档。完整功能已拆为22个独立验收项，见 `docs/product/SMART_RECOGNITION_SUBFUNCTIONS.md`。本轮优先实现日期/行动候选、版本化Review、确认后最小任务编译、旧分析主动核对、任务/日程门禁及移动确认面板。实际migration006为analysis_review_gate，文档原设想的Document迁移后续单独实施。

候选不直接变任务，UNKNOWN不变FALSE/TRUE；日期精度仅到日，具体时刻和缺年继续待核对；不按数组顺序编造DAG。未实现原件/行级坐标、图片高亮、真实RAG、完整排程草案与图像/PDF脱敏。每个子功能先独立测试，再验证API和移动连接，保留Offline Demo与工作区原有改动。

## 10 第二批代码实施进展

已落实文件原件/标准化行/授权预览和图片/PDF行区域高亮，migration007为document_line_evidence；与上一节的未实现状态相比，本批已完成这些连接。文件校验、PDF原生/扫描/旋转坐标、DOCX表格、失败原件保留、未使用原件删除与Demo清理均有独立测试。详细边界、命令和结果见SMART_RECOGNITION_SUBFUNCTIONS.md。网页原件、跨页表格结构、完整Privacy Guard、真实RAG与文件脱敏继续待做。

## 11 第三批代码实施进展

migration008及共享Profile类型契约已接入；所有硬条件合并、可选动作与资格区分、本地条件局部证据、模型语义候选和画像版本快照已实现。补齐独立测试与360/390px画像交互，保留Demo。当前只覆盖确定性资格匹配，兴趣软相关性、完整CampusEvent依赖及真实知识库仍待实现。原计划的迁移编号继续以实际006/007/008及后续序号为准。


## 12 第五至第七阶段实现对照

W5已完成有用户依据的耗时/分段、权重排序、工作偏好/限额/缓冲、周期课程、锁定、不可变草稿、原子commit及独立安排依赖/deadline门禁。W6已实现文件检测与永久副本；W7采用首版同步真实执行、实际重试/取消门禁及历史，不宣称可靠后台队列。W3补显式事实有效期/历史及软兴趣独立。W2补网页原件、附件父关系与混合PDF区域OCR。见SMART_RECOGNITION_SUBFUNCTIONS.md最新章节与独立测试入口。原Word原件保留，工程方案与API文档持续校准；模型/Embedding/设备效果仍需配置和环境验收。


## 2026-10-14 公开实例评测与阶段补充

已完成200份不同公开实例的真实DeepSeek评测及失败回归，197份通过结构/证据校验，3份短引不一致拒绝；不代表98.5%语义准确率，不属于模型训练。新增12份离线公开实例、17项有证据的行动；逐任务截止日期、6个画像字段及9类生成附件回归已落地。真实LLM移动浏览器链路通过，安卓真机仍缺设备。详见 [阶段报告](PUBLIC_CORPUS_200_VALIDATION_2026-10-14.md)。最新APK：`E:/ZhiShi/deliverables/Zhishi-RuleFlow-usb-debug.apk`，SHA256 `4460FE10E2834994518A4AE260360A6A84DF6796BB29C1AD431DA0D93D4DA9C8`。


## 2026-10-14 客户端资料五阶段补充

客户端画像、补充候选、可见资料卡、版本/备份/清理、本机匹配、单双周课表与确认后的占用时段排程、缺附件提醒和重新分析已接入。新一轮200多格式实例首轮174校验通过，失败回归后192通过、8拒绝；110个附件引用场景，40组课表回放无课程冲突。数据为受控格式转换，独立人工全文准确率未验收。后端151、前端58项测试及移动端流程通过；安卓真机暂缓。详见 [五阶段报告](CLIENT_WORKSPACE_FIVE_STAGES_2026-10-14.md)。当前APK SHA256：`7D4978905E9F0269A99C5930275684B32D3FCD6F4534219AE1626DCB1C1F598C`。
