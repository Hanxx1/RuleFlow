# 有绪 CampusWeave｜RF-013 正文入口与 CM-004 资料联调交接

核对日期：2026-11-27；C 侧代码走读与交接准备。基线：fetch 后的 `origin/main`，`f6aec68`。本文沿用已确认产品行为，不新增公共协议或代记 B 签认。

## 1. 正文提取入口与相关分支

| 能力 | 现有入口与版本 | 可用于联调的范围 |
|---|---|---|
| 网页获取与提取 | `POST /api/v1/import-batches/{batch_id}/sources/url`，请求 `{url,title?,consent:true}`；`main.py::_add_import_url_source → parse_url_blocks → parsing.py::parse_bytes → html_blocks` | 将公开网页获取、保存为来源和 Document；包含安全检查、用户授权和失败来源反馈。不是纯正文保证接口 |
| 已有单通知网页导入 | `POST /api/v1/imports/url`，同样经过 `parse_url_blocks` | 会进入既有 Case/分析链；双表来源移交优先复用批次流程，不能当作只读提取接口 |
| 已保存正文／真实行读取 | `GET /api/v1/import-batches/{batch_id}/form-context?expected_revision=<非负整数>`；`readFormContext`，位于 `mobile/src/features/imports/formContext.ts` | 只读当前账户当前批次；返回 `sources[].text/lines/text_origin` 及原件、解析、父引用状态；不重新抓取或清洗 |
| 附件原件读取和字节核验 | `readFormOriginal(context, sourceId)`，位于 `mobile/src/features/imports/formOriginal.ts` | 下载前后核对来源及 Document 版本，核验大小与 SHA-256 后交付 Blob；模板适配和导出决定由 B 负责 |

分支归属可由 Git 历史核对：

- `feat/RF-013-source-snapshot-core`：`e10f129`，快照服务，PR #36 合入。
- `feat/RF-013-form-context-http`：`f1bf3b4`，HTTP 读取；`feat/RF-013-form-context-client`：`ee25e39`，类型化读取，已随主线集成。
- `feat/RF-013-verified-original-read`：`de7a493`，原件字节核验，PR #40／`054a8d6` 已合入。原工作区仍停在该功能分支，不代表当前主线缺少此能力。
- `html_blocks` 的当前实现追溯至源码基线 `78d3130`；未发现另一个已实现“任意整页网页纯正文”的专用入口。已知本地及远端分支引用中未发现 CM-004 专用实现分支；本次只更新了远端 main，不将该检查解释为远端所有分支的实时清单。
- 本次文档分支：`docs/RF-013-CM-004-integration-handoff`，从 `f6aec68` 建立独立工作区；用户已授权提交并推送，实际结果以 Git 历史及会话回执为准，未创建 PR。

### 导航混入的实际边界

`html_blocks` 删除 `script/style/nav/footer/form`，依次查找 `.v_news_content`、`.wp_articlecontent`、`.article-content`、`.news-content`、`.entry-content`、`article`、`main`；无命中则回退到 `body` 或整个 soup。普通 div 中的导航文字不会被上述标签规则移除；选到过宽的 main 也可能包含无关段落。

本次直接调用现有函数的合成验证：同一份带 div 导航的 HTML，有 `article` 时返回 `['Notice body']`；正文也放在普通 div 时返回 `['Navigation', 'Notice body']`。这解释了当前反馈的一条可复现路径，未取得 B 的实际网页样本，不能断言真实样本必定走相同路径。

可立即联调：用户核对并粘贴通知正文，经 `POST /api/v1/import-batches/{batch_id}/sources/text`（`{text,title?,consent:true}`）保存，附件沿现有来源流程获取，再读取批次当前 revision 和 form-context。粘贴来源为 `legacy_text`，不生成 Document 行，不把显示行号伪装为正式 Evidence。已经保存的网页噪声不会因重读 form-context 消失；不得在消费端静默重排真实行后沿用旧 line_id。

`form-context` 保留已有 Bearer 鉴权及 `data/request_id` 包络；401、404、409 `IMPORT_BATCH_STALE`、409 `SOURCE_REFERENCE_INVALID`、422 等按真实错误处理，响应 no-store。原件存在与解析成功分开判断，完整约束见 [来源移交说明](records/C_RF013_source_handoff.md)。用户转达 B 已用真实校方正文和附件跑通双表填写及导出；这是 B 的联调反馈，本次未独立复现，不据此把网页净化、H06 全部边界或 H08 真机验收标为通过。

## 2. CM-004：交给 B 对齐的技术边界

既定产品行为以 [执行计划 2.1 节](../plans/TEAM_EXECUTION_PLAN.md) 和 [CM-003/004 任务卡](../plans/SPRINT_01_TASKS.md) 为准：一份资料关联多课；解除一课关联保留其他课程关系和共享原件；删课先预览，默认解除课程关系、停止对应上课规则，保留 Task、任务日程及原件；恢复默认保留当前值、补入有效缺失课程，冲突逐课选版；失效或离线无法核验的引用提示待核对。无需重新选择这些产品行为。

| 对齐项 | 当前事实及 C 侧交接意见 | 仍需 B／相关成员回核 |
|---|---|---|
| 稳定课程身份 | 正式本机档案是 `Workspace.courseProfiles[].id`（`CoursePreview.id`）；新增页用 `crypto.randomUUID()`，编辑保留 id。名称、学期是可编辑属性，不作为关联键；不同学期同名课程分别建 id | B 按当前账户与档案 id 消费，明确本机身份到服务端关联记录的验证方式；不能把旧 `Workspace.courses[]` 课表规则 id 或服务端 Schedule id 自动当成同一课程。跨端映射待共同评审 |
| 版本与账户 | Workspace v3 按 owner 分区，只有整体 `revision`，没有课程独立 revision；本机课程 id 不是服务端授权凭据 | B 说明关联写入和恢复检查所用版本、stale 处理及账户切换后的结果丢弃；公共存储及事务边界须按 RF-012 共同评审 |
| 资料身份 | 当前知识导入返回知识资料 `id` 与 `document_id`，检索结果另有 chunk 身份；Document 维护原件及版本。`source_id` 是导入来源身份，不能代替知识资料或 Document id | B 明确关联目标采用哪类正式 id、如何携带 Document revision/hash 及返回更新提示；关联表、DTO、URL 尚未在本轮批准或实现 |
| 权限与范围检索 | 服务端现有知识库和 Document 读取以会话 owner 授权；现有 `KnowledgeSearchIn` 只有 query/top_k/category，无课程或资料 ID 范围过滤字段 | B 提出限定授权资料集合的查询契约并补越权用例；不能先搜全库后由页面筛选来证明范围隔离。跨账户引用不披露私有名称、正文或原件内容 |
| 删除与恢复检查 | 本机课程页现有删除影响／恢复为只读预览；真实资料引用尚未接入。现有删除知识索引返回 `original_retained:true`，不等于已支持课程引用保护或完整生命周期 | B 提供资料引用检查、解绑及恢复后复核能力，C 消费结果串联页面，D 提供时间／Task 影响，A/B 协调公共接口和合并顺序。不得以现有删除知识索引入口替代删课解绑 |

### 失效引用反馈语义（接口表达待 B 回核）

下表沿用产品行为，中文分类仅用于评审，不是新增 API 枚举或已实现回执。

| 核验结果 | 页面应反馈及执行边界 |
|---|---|
| 当前账户下资料与关联有效 | 展示已核验资料；只在授权范围内查看／检索，不因本机存在 id 就认定服务端可读 |
| 资料或索引已删除、关联目标缺失 | 提示引用失效／待核对；保留获准的历史信息，不造可下载状态；知识索引消失与原件缺失分别表达 |
| Document 版本／hash 变化 | 提示资料已更新，旧依据需重核；不按同名资料自动替换引用，不把旧引用当作当前已核验 |
| 跨账户／无权读取 | 拒绝使用，安全提示无法读取；不返回其他账户的私有详情；不得仅凭备份中的 owner 或 id 授权 |
| 离线／网络失败／暂不能核验 | 标待核对，保留可用历史状态；不报“资料已删除”或“恢复全部有效” |
| 删除／恢复部分失败或结果未知 | 按项呈现已完成、失败和待核对结果；不报全部成功，不重复执行已成功项；具体查询、重试键、回执与跨端失败恢复方案待 B/C、A/B 评审 |

B 回核时需提供：采用的课程与资料身份映射、权限及范围过滤方式、版本检查、逐项核验结果和错误样例、对应分支／commit／测试证据。未实际获得 B 回复前，保持“C 已整理交接，技术接口待对齐”；不更改 D 的唯一公共决策表签认状态。

建议联调用例：两学期同名课；一资料两课且只解除一课；跨 owner 资料拒绝；资料改版／索引删除／原件缺失分别反馈；离线恢复待核对；并发 stale、取消零写入及逐项失败。上述 CM-004 用例是待验清单，本轮未执行真实关联测试。

## 3. 本轮验证与限制

本次仅文档更新、现有代码走读及合成函数验证，未修改业务代码、公共 API、存储或迁移。实际测试及文档检查结果统一记录于 [C 工作记录](records/C_notice_case.md)。未联系或代替 B 签认；真实通知样本、双表导出结果及原始会话证据待 B 提供可复查位置。无本次 APK。
