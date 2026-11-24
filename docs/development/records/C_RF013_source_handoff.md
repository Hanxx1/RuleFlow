# 有绪 CampusWeave｜RF-013 通知来源与填表移交准备

2026-11-09；负责人 C；基线 `ce597a1`；分支 `docs/RF-013-source-handoff`。
性质：现有 API 集成验证与 C/B 接口提案，未实现正式移交入口，RF-013/RF-011 整卡未完成。

**2026-11-24 评审补充：**用户转达 B 的消费意见并接受未变表保留输入、改版表旧值仅供对照及普通失败逐表处理的方向。C 的字段调整见文末第7节；替代早期以单一 `availability` 判定可填写性的建议。URL、最终字段、权限、错误、缓存与 OpenAPI 修改范围仍待 A/B 公共审查；H07 修复已合入，不再是待修前置。

**最新准备进展（2026-11-17）：**用户明确选择“尚未确认，先准备接口样例和回归测试”。本轮以最新 main `00d70a9` 创建 `docs/RF-013-form-context-preparation`，仅新增合成接口样例和10项目标回归，更新本说明与 C 工作记录；没有实现接口或修改 OpenAPI 基准。H07最小修复已另行提交为 `eef559b`，对应 [PR #18](https://github.com/Hanxx1/RuleFlow/pull/18)，本轮核对仍 open、未合并；以下11-10描述为历史快照，不能当作当前PR状态。

**进度同步：2026-11-10。**初始基线/分支和下文原始核查保留。来源移交提案 `6a6b20b` 已随PR #7进入main；H07诊断 `b179902` 已推送至 `docs/RF-013-recovery-validation`，对应 [PR #10](https://github.com/Hanxx1/RuleFlow/pull/10) 当前开放。最新fetch可见main为 `65977de`，尚未包含H07诊断提交；当前文档工作基线仍为b179902。**B/A/B尚未确认form-context；H07仅完成合成验证，发现两类未修复缺口。**详细命令、证据和后续顺序统一见 [C工作记录](C_notice_case.md)。本次没有修改团队公共决策状态。

## 1. 本轮依据与范围

- [团队执行计划](../../plans/TEAM_EXECUTION_PLAN.md)指定 C 负责 RF-013、RF-011 的 Document 侧，B 负责填表消费者和 RF-012 保存边界。
- [PR #5](https://github.com/Hanxx1/RuleFlow/pull/5) 的 `62ec31a` 已有本机多附件填写；B 实施方案的1C明确等待账户来源、原件和通知行移交。初始核查时尚未合并，现已进入main，不能再列为待合入业务。
- [PR #6](https://github.com/Hanxx1/RuleFlow/pull/6) 初始核查时开放、讨论列表为空；现已进入main。但C侧交叉评审的合入不等于A/B及全部消费者对公共方案完成签认。
- 仅准备批次到填表的读取边界与测试。Case 入口、共享引用登记/删除、正式草稿持久化和多候选迁移分别依赖 RF-002/011/012 等确认，不在本轮实施。

## 2. 已有能力与缺口

| 内容 | 当前代码事实 | 消费约束 |
|---|---|---|
| 批次来源 | `GET /api/v1/import-batches/{id}` 返回 revision 和 sources；`_import_source_json` 移除 extracted_text | 不能从标题、摘要重建正文；不能把 batch revision 当 source revision |
| 文件/网页 | source metadata 可含 document_id；`source_documents` 存正式关系 | metadata 不是授权凭据，须校验同 owner、当前 batch 和关系 |
| 文档元数据和行 | `GET /api/v1/documents/{id}` 返回 sha256、revision、lines；line 有稳定 id、行号及可空 page/locator | 原行 ID 必须保留；B 重排文本产生的显示行号不能直接冒充正式证据 |
| 原件 | `GET /api/v1/documents/{id}/content` 按当前登录用户授权、no-store | 元数据存在不代表原件可读；成功下载后再核对指纹、格式与模板映射 |
| 粘贴正文 | 文本来源只存 extracted_text 与 hash，未创建 Document；批次 DTO 不提供正文 | 现有公开 API 不足以完整恢复它；不得为旧文本伪造 Document/line/Evidence |
| 部分失败 | 文件逐份保存 ready/failed；失败源可删除并重新上传，批次 revision 递增 | 成功原件应保留；失败或仅发现的链接不能标为可填写附件 |
| 文档缺失 | content 返回 404，detail.code 为 DOCUMENT_CONTENT_MISSING | 显示原件不可用，引导重新选择/上传；不自动改用同名文件 |
| 解析失败但原件保留（H07新观察） | 受控parser失败时metadata有document_id、原件可下载，source_documents关联缺失 | 新读取接口不能只信任metadata或放松正式关系校验；先评审修复，历史数据兼容另议 |
| 附件返回HTML（H07新观察） | 下载候选返回登录/错误HTML时复用普通网页导入，被标ready并计入可分析来源 | 不能将其作为已取得有效附件交给填表；普通HTML通知仍是合法输入，修复须限定附件路径 |

源码入口：[main.py](../../../server/app/main.py)、[documents.py](../../../server/app/services/documents.py)、[batchStore.ts](../../../mobile/src/features/imports/batchStore.ts)。

## 3. 最小增量接口建议（待 B 及 A/B 公共审查）

建议新增只读 `GET /api/v1/import-batches/{batch_id}/form-context?expected_revision=...`，沿现有 `data/request_id` 包络。URL、字段和错误语义均未获确认、未实现，不要求 B 立即依赖。

用途：用户主动打开已保存批次的填表工作区时，返回本批次可读取的正文定位和附件引用，不创建 Case、Evidence、Task、草稿或触发模型/下载。先核对会话 owner 和 batch；不接收客户端 owner_id。只返回当前批次资源，不提供任意 document_ids 查询入口。

| 建议字段 | 语义 |
|---|---|
| schema_version、batch_id、batch_revision、case_id | 读取快照版本；case_id 可空，现有单 Case 信息不能扩展解释为候选绑定 |
| sources[].source_id、kind、status、error_code | 保留来源身份及失败原因；不按文件名去重 |
| sources[].content_hash | 表明 hash 的对象；文档原件 sha256 与粘贴文本 sha256 分开，不混用 |
| sources[].text_origin | document_lines 或 legacy_text；后者明确没有 Document 行定位 |
| sources[].text / lines | legacy_text 返回已存正文及 hash，lines 为空；文档来源返回原有 line_id、document_id、line_number、text 和可用定位，保留顺序 |
| sources[].document_ref | 无原件时 null；有原件时 `{kind: "document", id, revision, sha256, name, mime, size}`，沿 RF-011 的逻辑引用方向，不暴露磁盘路径 |
| sources[].parent_source_id | 仅在正式关联与 owner 校验后返回；网页附件须另行授权取得才有可消费原件 |
| sources[].availability | 区分可读、解析失败、原件缺失、仅链接待获取；读取快照不保证之后下载仍成功 |

附件用途、模板类别和适配版本由 B 使用实际原件指纹及用户选择确认。C 仅提供可核对来源，不新增与 B 并行的分类结果存储。规则适用对象绑定 source_id/document_ref，不能按“附件1”等展示文字自动绑定。来源范围不明确时待用户确认。

### 版本、权限与失败

1. expected_revision 与当前 batch revision 不一致建议返回 409，B 保留未保存编辑并提示重新读取，不静默覆盖。读取多表应取一致快照；下载后再比对实际原件 hash。
2. import_sources 无独立 revision，不凭空输出 source_revision。首轮以 batch revision＋source_id＋内容 hash，文档另用 Document revision/hash。增加来源版本须另审迁移。
3. 跨 owner、来源不属于批次、伪造文档关系拒绝，不泄露其他资源。客户端拿到 ID 之后，原件读取仍走既有鉴权接口。
4. 已有某一来源失败不遮蔽其他可用来源；旧正文缺定位、原件缺失、附件未获取分别提示，禁止拿空字符串当读取成功。
5. 原文内容仅在用户主动进入该批次工作区时发送当前客户端，不持久化到通用资料，不记录到日志，不调用模型。更进一步的外发仍走 Privacy Guard 与确认。
6. 本轮不改变 Document 删除语义，不承诺服务端知道所有本机草稿引用。RF-011 与 RF-012 须确认解绑、历史快照及本机引用不可见时的限制。
7. 已有 Case 的 Evidence 只能核对真实 Case/document/line 映射后携带；没有映射的 legacy_text 显示待核对，不能把 B 的本机显示行号转换成虚构 EvidenceRef。

## 4. 验收矩阵

| 编号 | 场景与目标 | 本轮状态 |
|---|---|---|
| H01 | 同名不同内容附件保持不同 source/Document/行集合，原件 hash 与内容一一对应；另账号不能读取批次及文档 | 新增现有 API 集成测试通过，样本为合成 TXT；未验证 Office 填写 |
| H02 | 一成功一损坏附件；移除失败源并补上传后成功原件不变，revision 增加，无提前 Case | 新增现有 API 集成测试通过；不是自动重试或新恢复 UI |
| H03 | 元数据仍在而原件文件丢失，明确返回 DOCUMENT_CONTENT_MISSING | 新增现有 API 集成测试通过，仅删除测试临时原件 |
| H04 | 旧粘贴正文读取，hash 可核对且不伪造行定位 | 新接口待确认、未实现、未执行 |
| H05 | 读取时 revision 冲突、伪造同 owner 的跨批次文档引用 | 新接口待确认、未实现、未执行 |
| H06 | B 同工作区恢复两份表、要求不串表、指纹不符阻断受影响表 | B 侧接入后联调，未执行 |
| H07 | HTML 登录页冒充附件、仅链接未获取、解析失败原件保留 | `b179902`合成探针：5项边界符合、3项OPEN_GAP，退出2；登录/错误HTML误标ready，解析失败Document缺正式来源关联；两类缺口未修复，非真实网站/Office验收 |
| H08 | 真实同一通知多份原表、Android 分享后的填表 | 依赖 B 样本与 A 真机组织，未执行 |

本轮命令与运行结果见 [C 工作记录](C_notice_case.md)。测试见 [test_notice_handoff_baseline.py](../../../server/tests/test_notice_handoff_baseline.py)。

## 5. 请用户转达的确认项与下一实施切片

- B：确认最小读取 DTO、legacy_text 无正式行引用的消费方式、附件用途由填表工作区确认，以及 H06 的共同样例。
- A/B：确认是否采用新增只读 form-context（避免扩大旧批次响应暴露范围），并核对正文读取用途及 RF-011/012 删除与草稿边界。
- D 及 A/B：RF-015 与 RF-038/039 的迁移顺序仍沿唯一公共决策表，本方案不预占迁移编号。

当前建议顺序（不是新授权或变更团队DDL）：

1. **先收口H07修复范围。**已完成合成复现，不重复把它列为“未选样”；B/A/B核对附件HTML失败消费及失败Document正式关系，确认后再在最新main上开小修复分支。修复触及 `main.py`，须保护最新main已有的 `9b1d2ae` 重试排序增量；它没有修复这两类缺口，且本次未重新运行其新用例。
2. **form-context共同确认后实施H04/H05。**只读服务/API及权限、版本、一致性测试；不先迁移数据库或改B页面。失败源必须区分原件仍在、未取得和原件缺失；legacy_text不伪造Document行。不能以H07准备或PR开放代替接口批准。
3. **B接1C后联合验证H06，再按条件验H08。**用已核验真实原件检查同一工作区多表恢复、要求不串表及指纹失效；Android由A组织。未具备设备或共同样本时如实保留未验范围。

当前仍需的输入：B确认附件失败状态和读取DTO的消费方式；A/B确认公共 `main.py` 两类修复范围及读取用途；B/C确认RF-011/012引用删除/草稿不可见边界；A/B/C/D按唯一决策表协调RF-015与RF-038/039迁移顺序。CM开发按用户要求暂停，既有课程提案不在本次展开。

本次只同步C的技术说明与本人工作记录，未执行产品功能测试，未修复缺口、创建共享API或更新契约基准。诊断及12项定向回归结果仅适用于原记录所列基线；本轮文档检查结果见C工作记录。

## 6. 2026-11-17 可评审接口样例与 RED 回归

本节细化第3节的待确认方案。用户尚未转达 B 与 A/B 的确认，以下错误码、字段及状态值均为**提议和测试目标，不是正式协议**。不将已有 H07 修复范围的授权扩展到此接口。

- [合成请求／响应样例](evidence/C_20261117/form_context_samples.json)：旧粘贴正文、Document原行、版本冲突和非法引用四例，以及可用性状态与待决策清单；示例ID不是正式EvidenceRef，样例回执不是实际运行结果。
- 本地目标回归 `server/tests/test_form_context.py` 有 10 项用例，复用隔离账户、内存 SQLite 与合成 TXT/PDF 输入。实测均因目标路由尚未实现而失败。测试文件留在本地，待接口实现后与实码一起评审。具体命令与结果见 C 工作记录。

### 请求与读取范围（待确认）

`GET /api/v1/import-batches/{batch_id}/form-context?expected_revision=<非负整数>`；沿现有Bearer登录、`data/request_id`成功包络。先校验owner及batch，再比较revision、读取本批次来源／正式Document关系／原行的一致数据库快照。零写入、不下载外链、不调用解析器或模型、不生成Case、Evidence、Task或草稿。来源未提供独立revision，不新增伪字段。

来源字段按第3节细化：`source_id/kind/status/error_code/content_hash/text_origin/text/lines/document_ref/parent_source_id/availability`。`schema_version`建议为整数1。`document_ref`只返回第3节所列元信息，不含磁盘路径；line输出`line_id/document_id/line_number/text/page/locator`及已有可用定位，不能把客户端显示行号当作真实line_id。首批回归只覆盖真实行ID／顺序／Document归属，完整定位字段及父引用还需后续实现时补测。

hash的对象必须明确：`legacy_text`为UTF-8已存正文的hash；`document_lines`对应原件hash，不是重新拼接行文本的hash。这里的原件hash来自Document记录，B下载实际原件后另验字节hash，不把本接口称为实时文件完整性验证。数据库快照不保证文件稍后仍存在或可下载。

### 失败与引用边界（待确认）

| 场景 | 建议结果 | 首批回归范围 |
|---|---|---|
| 未登录、他人批次或不存在批次 | 401／404；先做owner校验，不泄露正文 | 已写目标断言，当前路由不存在，未通过 |
| 未传、负数expected_revision | 422；不默认忽略版本 | 已写目标断言 |
| revision不符 | 409／IMPORT_BATCH_STALE，客户端保留编辑重读 | 已写目标断言 |
| metadata与正式关系不符、关系缺失／owner不符、Document跨owner | 建议整次409／SOURCE_REFERENCE_INVALID，不返回其他来源内容、不自动补关系 | 四项参数化目标断言；整次拒绝策略待共同确认 |
| 原件缺失 | 200，受影响来源标original_missing；保留可用原行与引用，其他来源正常 | 已写目标断言，不等于下载可用 |
| 正式关联的解析失败Document | 200，parse_failed、保留原件引用及error_code，text=null、lines=[] | 合成fixture显式建立正式关系，避免把未合并PR #18当成本分支已有实现 |
| 文件从未取得Document | 200，not_acquired、document_ref=null，不伪造可读正文 | 用损坏PDF构造目标断言 |
| metadata有Document但历史正式关系缺失 | 建议拒绝；不能通过放松校验伪造归属 | 已写缺失关系断言；历史兼容需另定方案 |
| 父来源、文件与数据库并发变化、调用无副作用 | 父引用同owner同batch；一致快照、读取零业务写入；文件状态如实降级 | 已写重复读取及数据库不变断言；并发、父引用和无网络/模型调用的专门断言仍待补充 |

成功响应及明确业务错误建议设置`Cache-Control: no-store`；未登录和框架参数校验响应的缓存头是否一并统一，需在接口评审时明确，不擅自改全局中间件。没有原件的未授权附件候选仍只是父来源metadata中的候选，不能为它自动创建source或标记已取得。

### 11 月 20 日 B/C 联调核对

沿用本节的接口样例。B 对照填表页标出每张表实际消费的字段，C 对照来源记录解释字段取值。以下场景中的填写体验待共同决定；状态码和字段仍以本节提议供核对。

| 用同一份通知和两张表核对 | 读取端可提供或区分什么 | B/C 要一起走查的用户操作 |
|---|---|---|
| 通知更新，用户已填了一半 | 请求中的 expected_revision 与当前批次 revision；旧粘贴正文只有 text，正式文档才有可定位的 lines | 提示重读时如何保留当前输入，哪些要求变化后要重新核对 |
| 第一张表的附件没有取得、解析失败或原件已丢失 | availability、error_code、document_ref；已取得但解析失败仍可有原件引用，可读原行和可下载原件分别判断 | 第一张表展示哪类提示，已有填写值能否暂存；第二张有效表能否继续 |
| 重新选取同名但内容不同的附件 | 用 source_id、父来源、Document 引用和原件 hash 对应具体表；B 下载后核验实际字节 | 哪些填写值可以沿用、哪些需要用户重核，如何避免把第一张表的值带到第二张 |

RF-012 当前沿用退出清理行为。上述“保留当前输入”需要区分当前页面、刷新后和重新登录后三种情况；后两项依赖 B 的保存与恢复方案。现阶段可先用合成样例核字段、复跑现有附件失败回归。

### 共同确认后才实施

B核字段消费、正文／原行及多表恢复预期；A/B审URL、读取用途、错误策略、缓存及OpenAPI增量。确认后再实现服务与路由，补一致快照和剩余边界测试，审查新增路径的OpenAPI差异，获准后更新指纹。H06填表联调及H08真机验收不在这批RED准备结果内；不提前改B页面、存储、迁移或历史数据。

### 11 月 22 日开工复核：版本和父来源（待确认）

基线为 `3bcd0d7`。PR #18 已合入。本地目标测试现在验证现有上传接口确实为解析失败原件建立了正式关系，移除了此前的测试补写。读取端仍按当前 owner、来源、正式 Document 关联判断原件归属。

| 决策 | 现有 API 实测 | 首版建议与验收 |
|---|---|---|
| 批次版本能承诺什么 | 附件获取开始后 revision 已推进，模拟网络读取时只有父来源。附件请求完成后同一 revision 下有两条来源。 | 在一个数据库读事务内核对 owner、revision、来源、关系及行。`expected_revision` 仅作批次版本检查。若 B 需判断两次读取的实际来源是否一致，建议将首次响应中 `source_id`、正文或原件 hash、Document 版本及可用性作为逐表复核依据；续填、下载或提交前重新核对。若团队要求同一 revision 永远代表同一来源集合，需另审来源写入与版本推进的事务边界。验收应覆盖获取中和获取后两次同版本读取。 |
| 父来源已被删除 | 成功删除未分析批次的父网页后，子附件与其正式 Document 关系仍保留，metadata 仍指向已删除父来源。 | 建议只返回经验证的同 owner 同批次 `parent_source_id`。缺失的父来源将返回空值并标为「父来源待核对」（状态字段待定），有效附件仍可核查原件。已查到但属于另一批次或账户的父引用按非法引用处理，响应不暴露其 ID 或内容。验收分别覆盖正常、已删除及非法父引用。 |

B 请确认逐表复核是否足以支持填表期间的编辑保留，以及父来源缺失时是否允许继续使用已选择的原件。A/B 请确认上述两项处理、接口 URL/字段和错误策略，以及首版是否只改读取服务、路由、定向回归和经评审的 OpenAPI 基准。确认意见应记录所审版本和选择。

## 7. 2026-11-24 B 消费意见后的 C 侧调整（待最终公共评审）

依据为用户在本会话转达的 B 意见及用户体验方向选择，不代签 A/B 的公共接口批准。远端核查 main 为 `dbc514d`；[#30](https://github.com/Hanxx1/RuleFlow/pull/30) 的来源边界和已合并 [#33](https://github.com/Hanxx1/RuleFlow/pull/33) 的草稿缺陷复现继续复用。以下字段是待 B 回核的修订提议，未改正式 API、OpenAPI 或本地 RED 测试。

### 7.1 来源身份与要求绑定

- 当前账户分区内以 `batch_id + source_id` 标识一份附件，`document_ref.id + revision + sha256` 核对原件版本；同名或字节相同的两个来源仍是两份表。重排不改身份，移除后重新上传形成新 source 时不凭文件名或 hash 自动接回旧草稿；本机尚未上传的文件身份由 B 的页面方案解决，C 不伪造服务端 source_id。
- C 提供来源 `name`（展示）、原文、真实行 ID、Document 引用、经校验的父子关系及各自状态。文件名或原文附件编号只是匹配提示，不是身份或授权依据。只返回批次中真实存在的来源，不为未取得的网页附件候选造 source。
- B 从通知原文提取要求，在本次填写快照中保存「要求来源 source_id／版本或正文 hash／真实 line_id（如有）→目标附件 source_id 集合→用户核对结果」。这是 B 的消费模型建议，不新增 C 接口的自动规则归属字段，也不在本轮引入正式草稿存储。共用要求显式指向 A、B 两个 source；“附件一”对应不清时由用户选择，不能按数组序号推断。legacy_text 可显示原句与 hash，但无正式行引用的要求仍标待核对。
- 逐表复核同时检查目标附件和其依赖的通知来源／要求绑定。共用通知变化时，保留受影响表输入、撤销导出确认并重新核对；只新增无关来源不自动清空其他表。原件版本改变、权限失效或复核请求失败则暂停该次导出。已获确认的页面保留方向不等于刷新／重新登录恢复获批；后者仍归 RF-012。

### 7.2 原件与正文分开表达

保留现有来源 `status/error_code` 表示导入处理情况；不能用它或单一 `availability` 决定能否填写。建议将读取 DTO 中的 `availability` 替换为下列对象，配合既有 `text_origin/text/lines/document_ref`；不改数据库状态枚举。

| 提议字段 | 值与语义 |
|---|---|
| `original.state` | `present`：读取时观察到原件存在；`missing`：Document 有效但原件缺失；`not_acquired`：尚无原件；`not_applicable`：直接粘贴文本本来没有文件；`unverified`：存储暂时无法核验。`present` 不是下载成功或可导出的保证。 |
| `original.error_code` | 缺失／暂时不可核验的安全原因，正常为空；不含磁盘路径。原件读取仍走现有鉴权 content API，B 在实际下载后核字节 hash。 |
| `extraction.state` | `available`：有已存正文或真实行；`failed`：解析失败（含不支持的格式，具体原因见 error_code）；`empty`：解析未产出正文；`not_acquired`：尚无可解析输入。与原件存在与否独立。 |
| `extraction.error_code` | 解析错误或空结果原因，正常为空；与原件读取错误分别保留。读取接口不重跑解析。 |
| `parent_reference_state` | `none`：本来无父来源；`valid`：同 owner 同 batch 的父来源存在；`missing`：原父来源已删。仅 `valid` 返回 `parent_source_id`；非法父引用整次拒绝，不返回其标识符。 |

例如：解析失败且原件存在＝`original.present + extraction.failed`，保留合法 document_ref；B 能下载、核验并识别模板时可继续填。原件缺失但历史原行仍在＝`original.missing + extraction.available`，允许展示获准原句，暂停依赖原件的导出。旧粘贴正文＝`original.not_applicable + extraction.available`，不错误提示原件丢失。父网页已删不等于附件原件缺失，不能用父状态覆盖附件状态。

### 7.3 错误与继续操作边界

| 场景 | C/B 对齐后的建议行为（最终错误包络待 A/B 审） |
|---|---|
| batch revision 不符 | `409 IMPORT_BATCH_STALE`，保留当前页输入，重读后逐表复核；不能只校验 revision。同版本新增来源仍须读到并检查依赖变化。 |
| 当前用户无权读取批次 | 沿现有 401／404 门禁，不返回正文或来源信息。 |
| 跨 owner／批次、伪造或缺失正式 Document 关系、非法父引用 | 建议整次 `409 SOURCE_REFERENCE_INVALID`；不返回部分来源内容或越界 ID，不自动修关系，保留页面输入并暂停依赖该响应的操作。授权错误不能降为普通坏附件。 |
| 原件未取得／缺失、解析失败／格式不支持 | 整体读取可成功，逐来源返回两个独立状态；只限制受影响表所需的操作。解析失败不自动禁止使用有效且可核验的原件。 |
| 父来源已删，子附件正式关系仍有效 | 返回 `parent_reference_state=missing`，可核验原件继续填写。若命名、字数或提交要求只能从丢失父通知核实，允许保留当前草稿，暂停按通知确认导出；不把旧确认当作当前有效。 |
| 原件存储暂不可核验／复核请求失败 | 不把 I/O 或网络故障当成确认丢失；保留输入，暂停该次相关导出，允许之后重试核验。 |

成功和明确业务错误建议 `no-store`；401／422 的覆盖范围、父状态字段名、最终枚举及错误码仍待 A/B 与 C 审定。一次数据库一致读取与稍后的文件下载之间仍存在变化窗口，首版不承诺原子锁定整个导出流程。

**验收补充（预期，未执行）：**同字节双表不同 source、仅调序保留两表；只换 A 时 B 保留、A 旧值不自动带入；同 revision 获取中新来源；共用通知变化保值但撤销确认；解析失败仍可核原件；原件丢失仍可读历史行；坏附件逐表与非法引用整次拒绝；父来源缺失且要求不可核时阻断通知导出。#33 仅证明缺陷复现，修复后的断言由 B 随实际实现更新。现有样例 JSON 已按本节调整，均为提议而非运行结果。

**待 B 回核：**要求绑定快照所需字段、移除重传的新身份处理，以及上述原件／解析／父引用状态能否覆盖页面操作。反馈后交 A/B 审最终读取接口范围，不在本轮扩充正式存储或来源写入事务。

### 7.4 11 月 24 日继续开发：内部只读快照切片

用户要求基于对接继续开发。先落地 C 内部 [notice_source_snapshot.py](../../../server/app/services/notice_source_snapshot.py) 的 `read_source_snapshot`，由调用方提供已认证 owner、SQLite连接、批次版本和原件根目录。该函数尚无正式路由消费者，不是已发布 DTO／错误协议，不改变本节最终公共评审边界。

使用 SAVEPOINT 读取同一数据库视图，按 owner 校验批次及所有来源、正式原件关系、文档／行和父引用；全部关系通过后才检查文件。保留真实行ID、页码及已有坐标；旧粘贴正文不造行。原件仅探测文件状态、不读字节、不重新解析，present 不等于可下载保证。服务不提交或回滚调用方原有事务，不创建 Case/Evidence/Task，也不生成 B 的规则绑定或导出决定。

[21项内部服务测试](../../../server/tests/test_notice_source_snapshot.py) 覆盖身份、状态、权限／引用、零写入及无抓取／解析／模型调用、调用方事务保护和真实双连接 WAL 读取：首次读取中另一连接在同 revision 新增来源，当前读取保持旧视图，下一次读取看到新增来源。正式 route、缓存头、错误状态映射和 OpenAPI 仍未接入；原10项 HTTP RED 目标保持不变，不拿服务通过当作它们已通过。实际命令和回归范围见 C 工作记录本日续记。
