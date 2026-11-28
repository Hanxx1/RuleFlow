# 有绪 CampusWeave｜RF-014 多候选输出校验准备

日期：2026-11-28；C；分支 `feat/RF-014-candidate-validation`，基于 fetch 后 main `bbeb9a4`。本切片是未接入线上流程的内部实验，供 B/D 及 A/B 评审。下列模型、字段和错误代码不是已批准的公共 DTO、Provider 协议、数据库结构或执行回执。

## 范围和调用前提

`server/app/services/notice_candidate_validation.py` 提供：

- `validate_candidate_output(payload, snapshot, allowed_course_ids=...)`：校验内部候选输出，返回只读预览元组，任一候选不合法则整次报错。
- `preview_candidate_output(generate, snapshot, allowed_course_ids=...)`：供 Fake Provider 用例注入输出；未配置或超时明确报错，不返回 Demo。

调用方须先用当前认证账户、批次及预期版本调用既有 `read_source_snapshot`，传入该服务实际返回的快照。可用课程 ID 必须来自同一身份下读取的课程档案；本模块不读取 Workspace，也不把课程 id 视为服务端授权凭据。**不得将客户端或模型自行提供的 snapshot／课程集合用于资源授权。** 纯校验本身不能独立证明 owner 权限或快照仍最新；未来执行前需再次核对。

没有路由或业务页面导入本模块；没有改 `LLMProvider`、`AIAnalysis`、既有单 Case 分析、导入、Review 或确认链。未调用模型，不写候选、Case、Evidence、Task 或草稿，不读取文件或触发下载。原件存在性和来源授权沿用既有服务，不在这里另建来源系统。

## 当前内部模型与检查

输入只有批次身份／版本和候选列表。每条候选暂含候选 id、kind、标题、可空课程 id 及来源引用；来源引用保留 `source_id`、`content_hash`、Document id／版本、真实 line_id 和原句。字段为本实验工作模型，不对应正式 Case、Task 或 EvidenceRef。

| 检查 | 本轮行为 |
|---|---|
| 结构和边界 | 严格类型、禁止未知字段；最多 20 个候选、每项最多 20 条引用，标题最多 300 字符、短引最多 2000 字符；布尔值不能冒充版本整数 |
| 候选身份 | 不接受重复候选 id；同标题不同课程不合并。模型不能通过 owner_id、case_id、evidence_ids 或 selected 字段声称已授权／已执行 |
| 课程归属 | case 建议不带课程 id；task／requirement／knowledge 建议须明确指向调用方提供的可用课程 id。只验证候选归属，不执行这些操作，不验证它们已经是合法 Task 或资料关联 |
| 来源身份和版本 | 引用须属于本快照；逐项核 source_id、hash、Document id／revision。相同 batch revision 下的来源变化仍需逐来源检查；新 source_id 不因同 hash 继承旧引用 |
| 原句和原行 | Document 引用须匹配该 Document 下唯一真实行，短引须是该行的精确子串；同文档另一行的文字不能替代指定行。重复来源身份、行身份和重复引用拒绝 |
| 旧文本与失败源 | legacy_text 校验已存文本的 hash／原句，Document 和行引用必须为空，标定位待核对；failed／empty／not_acquired 解析状态不可当可用正文 |
| 原件／父来源缺失 | 原行仍可读时保留历史短引，增加待核对原因；不自动视为可下载、可导出或可执行 |
| 资格与确认 | 输出资格固定 UNKNOWN，保留用户核对要求。模型输出 TRUE／FALSE 等资格字段整体拒绝，不能用结构检查替代三值规则计算 |
| 模型失败／空结果 | 已知 AIUnavailable 或 TimeoutError 转为固定安全错误；不泄露原始异常、不自动重试、不返回样例。合法空候选保持空列表 |

`CandidatePreview` 及来源引用只读，不回写输入。所有已校验结果仍带 `USER_REVIEW_REQUIRED`：原句存在不等于标题、事项边界或归属在语义上正确，更不代表资格符合或允许执行。当前没有解析或校验行动、日期、材料字段和规则 AST，避免提前复制现有能力或发明新协议。

## 合成样例与验证

[评审样例 JSON](records/evidence/C_20261128/rf014_preview_samples.json) 使用一个合成 Document 三行，分别对应春季线性代数作业、秋季同名课程作业与普通助学金事项。两个课程 id 分开，标题相同也不合并；所有 ID 只是内部样例，不是可调用的业务资源。JSON 对应的原件 hash 为三行 UTF-8 合成文本摘要，不是某个校方真实文件。

新增 [定向测试](../../server/tests/test_notice_candidate_validation.py) 覆盖一来源两事项、两课＋普通事务、三类课程建议、越界字段、身份及版本、错行原句、重复／空／超限输出、失败 Provider、只读返回、旧文本和失效来源。另以既有真实上传／快照服务建立隔离合成来源，验证跨 owner 快照拒绝，校验前后数据库逐行不变；这不是新候选 HTTP 接口测试。

实际命令、结果和失败修正统一见 [C 开发记录](records/C_notice_case.md)。当前 43 项新增测试与既有 AI、来源快照、form-context、来源迁移基线共 95 项通过；OpenAPI 保持原接受基线。未运行完整后端、前端构建、真实模型、B 页面或 Android。

## 下一步评审与限制

1. B/D 核 source_ref、旧文本、课程归属、同名不同学期及 UNKNOWN 消费语义；A/B 按既有规则协调正式输出协议。上述枚举和字段不得直接当作公共定稿。
2. RF-008 公共能力、调用记录／去重／预算、隐私授权及超时控制另行评审；本轮 Fake Provider 接缝不实现 RF-009/010，也未验证真实模型效果。
3. RF-014 还缺实际多事项识别、字段内容／语义验证和消费者接入。RF-015 存储、分析版本、确认回执及 RF-016 事务仍按 [RF-002 提案](records/C_RF002_contract.md)与 [D 唯一决策表](records/D_public_interface_questions.md)确认后实施。
4. CM-007 的现有页面模型继续为样例；不将这个内部预览传给 Case／Task／知识执行器。无取消／重试／版本确认或“部分执行成功”功能，不创建第二套正式执行机制。

用户已授权提交并推送本切片，具体提交由本分支 Git 历史追溯，推送结果以本次会话实际回执为准；未创建 PR，RF-014 整卡未完成。正文修复 `9031dea` 尚未在本次 main 基线，未将其当作本切片的已合入依赖；本模块消费既有来源快照，与该解析修复无代码依赖。

## 2026-11-28 续：候选内容校验内部切片

本节是前述实验的后续增量，仍不是公共 DTO 或已接入功能。新增 [内容校验模块](../../server/app/services/notice_candidate_content.py) 和 [51 项合成测试](../../server/tests/test_notice_candidate_content.py)，复用当前分支 `350d00c`；尚未提交、推送。

1. 已授权快照 → `validate_candidate_output` → `candidate_content_sources(candidate)`：仅暴露本候选已核验的短引。每个 `ContentSource` 提供 `local_ref`、`source_ref_index` 和 `text`；本地别名的摘要覆盖候选身份、标题、课程及来源版本／短引，防止不同候选或版本偶然复用。别名使用既有校验器接受的语法，但**不是正式 EvidenceRef，不得写入 Case／Review／Task**；索引只定位回原候选的引用元组。
2. `validate_candidate_content(candidate, payload)` 接受现有 `AIAnalysis` 形状的内部草稿，严格类型校验；规则／材料／行动及出现的语义字段必须有完整、无重复的声明引用和逐字短引，不能借同一文档中另一候选或另一行的文字。复用 `validate_ai_payload/validate_candidates` 的白名单、画像类型和已有语义检查；未修改公共 `ai.py`、Provider 或单事项分析。额外限制 AST 深度 32、节点 256，并要求叶节点有当前规则的引用。
3. 日期只对候选短引调用已有 `extract_dates`；保留缺年份、非法日期、时区和多日期的既有待核对结果，不补年份／时间，不自动分配到任务。模型传入非空 `Task.deadline` 被拒绝，即使与提取值相同；时长仅作为待确认建议。材料状态沿用 missing／optional／unknown，不允许模型宣称已取得。
4. 返回冻结的 `CandidateContentPreview`：内容与日期保存为 JSON 字符串快照，避免调用方修改嵌套结构；资格固定 UNKNOWN，保留原来源待核对原因。别名摘要不代替权限、新鲜度或正式确认；调用方仍须取得授权快照，执行前重核来源。

最终相关回归 **160 passed，5 warnings**，其中本轮新增 51 项；包含真实 API 上传合成 TXT → 来源快照 → 候选 → 内容校验，并比对数据库 dump 不变。首次 45 项定向、后续 157 项回归和最终结果的环境／命令见 C 原任务续记；沙箱首次无输出运行已中止，不计通过。

未调用真实模型、未修改路由／数据库／公共协议／前端；本轮未运行完整后端或 Android。标题与短引的完整语义、事项拆分效果、附件适用范围、正式输出协议、Provider／预算／去重、候选持久化和确认执行仍未完成；已有内容结构检查和受保护规则语义核对不等于全面语义正确。下一步需 B/D 回核并由 A/B 协调公共输出和接入范围，之后才接真实 Provider 与消费者；RF-015／016 迁移与事务仍沿用唯一决策表。
