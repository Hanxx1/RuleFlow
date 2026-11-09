# 有绪 CampusWeave｜RF-013 通知来源与填表移交准备

2026-11-09；负责人 C；基线 `ce597a1`；分支 `docs/RF-013-source-handoff`。
性质：现有 API 集成验证与 C/B 接口提案，未实现正式移交入口，RF-013/RF-011 整卡未完成。

## 1. 本轮依据与范围

- [团队执行计划](../../plans/TEAM_EXECUTION_PLAN.md)指定 C 负责 RF-013、RF-011 的 Document 侧，B 负责填表消费者和 RF-012 保存边界。
- [PR #5](https://github.com/Hanxx1/RuleFlow/pull/5) 的 `62ec31a` 已有本机多附件填写；B 实施方案的 1C 明确等待账户来源、原件和通知行移交。该 PR 在本轮核对时未合并。
- [PR #6](https://github.com/Hanxx1/RuleFlow/pull/6) 在本轮核对时开放、讨论列表为空，C 侧交叉评审尚未成为团队公共签认。
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
| H07 | HTML 登录页冒充附件、仅链接未获取、解析失败原件保留 | RF-013 下一修复切片待选样及复现，未执行新探针 |
| H08 | 真实同一通知多份原表、Android 分享后的填表 | 依赖 B 样本与 A 真机组织，未执行 |

本轮命令与运行结果见 [C 工作记录](C_notice_case.md)。测试见 [test_notice_handoff_baseline.py](../../../server/tests/test_notice_handoff_baseline.py)。

## 5. 请用户转达的确认项与下一实施切片

- B：确认最小读取 DTO、legacy_text 无正式行引用的消费方式、附件用途由填表工作区确认，以及 H06 的共同样例。
- A/B：确认是否采用新增只读 form-context（避免扩大旧批次响应暴露范围），并核对正文读取用途及 RF-011/012 删除与草稿边界。
- D 及 A/B：RF-015 与 RF-038/039 的迁移顺序仍沿唯一公共决策表，本方案不预占迁移编号。

确认后的第一实现切片：只读 form-context 服务/API＋H04/H05 的权限/一致性测试；不先改数据库或 B 页面。之后由 B 接 1C，C 配合正文/引用错误处理与联调。H07 应先用受控输入复现，再单独提修复。
