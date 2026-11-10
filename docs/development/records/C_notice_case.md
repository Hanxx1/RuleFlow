# 有绪 CampusWeave｜成员 C 开发工作记录

## CM-001｜课程公共契约与混合输入样例（2026-11-10）

### 1. 任务信息

- 负责人 C；协作：D 提 Task/时间消费，B 提 Workspace/资料消费，A/B 协调公共评审。
- 目标：补齐课程身份、要求四态、来源历史及混合建议的 C 侧输入，使 CM-002 页面样例和后续跨模块评审有共同素材。
- 基线 `d1d8647`（2026-11-10 fetch 后与 origin/main 一致）；实际分支 `docs/CM-001-course-contract`（按用户纠正使用 CM 任务编号）。状态：**C 侧提案与合成样例已准备，待共同评审，CM-001 整卡未完成**。用户已授权提交并推送这两份文件；实际提交及远端状态以 Git 记录为准，本轮不创建 PR。
- 对应 [近期任务第5.4节](../../plans/SPRINT_01_TASKS.md#54-新增-cm-近期任务卡)；11-13 是共同确认检查点，不会到期自动批准。

### 2. 技术实现

- 本节是 C 的提案与操作矩阵；[cm001_samples.json](evidence/C_20261110/cm001_samples.json) 提供同名跨学期、一课两规则、要求四态、两课程＋普通事务、共享资料及8组评审场景的合成输入。JSON 中字段名仅用于样例表达，**不是已确定的 DTO、Schema、URL 或持久化格式**。
- 走读 `mobile/src/services/clientWorkspace.ts`、`timetable.ts`、`router.ts` 和 B/D 记录：Workspace v2 按 owner/revision 保存；旧 Course 同时含课程名及一条 weekday/startTime/endTime 规则，`expandCourses` 用旧 Course ID＋日期生成发生时段。当前没有可直接复用的独立学期/课程要求历史实体。
- 未修改正式业务代码、共享类型、路由、Workspace、数据库、AI、Android 或其他成员记录；未实现课程保存或新 API。

### 3. 设计与关键决策

以下是 **C 推荐方案，等待对应消费者及 A/B 确认**。产品方向按开发指导第11节执行；正式决策状态仍以 [D 唯一公共决策表](D_public_interface_questions.md) 为准。本节提供输入，不是第二份已批准协议；评审结果由 D 写回对应 Q 行。

#### 课程身份与关系建议

| 对象 | C 建议的最小关系与版本边界 | 消费/待确认职责 |
|---|---|---|
| 学期 | owner 下稳定身份，显示名称与起止日期；修改名称不换身份，同一名称不作为唯一键。具体作息/周次基准由 D 定义 | B 确认 Workspace 保存/恢复，D 确认周次，A/B 审公共关系 |
| 课程档案 | 稳定课程身份引用一个学期；名称、教师/地点等普通字段与自定义字段分开。一课换名保持身份；跨学期同名保持独立，不用标题去重 | C 提案；B 审保存/迁移；D 消费课程身份；对应 Q01/Q08-d |
| 课程要求 | 课程下稳定要求身份；常用项固定展示（考勤、考试/评分、实验、分组、项目、作业），自定义项有独立身份；同名自定义项先提示用户，不自动合并 | C 实现要求交互，B 核 RF-012 版本保存；对应 Q02/Q10 |
| 上课规则/发生时段 | 课程一对多上课规则，每条规则有身份与版本；具体发生时段保留规则/日期/版本映射。课程档案不复制 D 的排程逻辑 | D 定义规则、取消单次/时区/唯一占用映射，C 消费编辑/影响；对应 Q04/Q08-d |
| Task | 引用 D 的同一 task_id；课程关联与 origin/case_id 分开，不制造 Case。建议首个切片每 Task 最多一个主课程，知识资料可多课关联；多课程共同作业的 Task 关联基数尚待共同决定，不能据此删减需求 | D 提接口，C 核来源/Review，B 核引用；对应 Q01/Q02，正式实现等 RF-038/039 |
| 资料 | 课程与已授权 Document/知识资料多对多关联；取消一课关联保留原件和其他课程关系 | B 实现 CM-004，C 对齐 RF-011/050；对应 Q02/Q05 |

**版本建议：**课程档案、要求历史、时间规则、候选操作分别表达实际依赖的版本，Workspace 整体 revision 继续作为存储并发保护；不把新的实体 revision 当成已有字段。写入检查期望版本，冲突时保留用户输入并重新核对。具体新增版本粒度、保存位置及事务边界归 RF-012/CM-001 评审，不能先改 Workspace v2。

**旧 Course 兼容建议：**不根据同名/同教师猜测合并。先逐条保留旧 Course ID 与原规则/依据，迁移预览让用户确认哪些规则属于同一课程及学期；保留旧 ID 到新课程/规则的映射，以免旧发生时段和备份引用失效。未能确认的记录保持旧课表能力，不隐式生成正式课程档案或 Task。D 评展开/占用映射、B 评升级恢复，迁移编号与合并顺序由 A/B 协调；本轮不迁移。

#### 要求四态与历史建议

| 显示状态（样例值） | 保存/显示含义 | 来源与确认要求 |
|---|---|---|
| 未记录（unrecorded） | 未提供有效要求；值可空，不展示为“无要求” | 可以没有来源；不能自动转为明确无要求 |
| 待核对（needs_review） | 提取歧义、冲突、来源缺失/失效，或尚未人工确认 | 保留可用原句、缺失原因和候选值；缺依据不补造行号 |
| 明确无要求（explicit_none） | 针对当前项明确声明不要求，不是空字符串 | 须用户确认并保存教师原文或用户声明；界面区分两类来源，不伪装官方依据 |
| 已确认（confirmed） | 用户已核对的当前有效内容，不等于学校审核通过 | 保存确认版本及来源；有来源的提取仍须确认，不由 AI 自动提升 |

状态文字是产品要求，英文值只是样例标签。新 AI 建议一律先进入待核对，不能直接改为后两态。简单编辑和复杂规则编辑使用同一份版本化内容；自定义字段不扩展 Rule AST 白名单、不执行表达式。小组只记录成员/分工和任务引用，不建在线协作权限系统；真实成员信息不进入公开样例。

历史建议按“旧值/状态/版本 → 新值/状态/版本＋操作者来源＋变更理由＋依据快照”追加。新通知先展示差异，不覆盖用户确认值；例如样例中的“闭卷→开卷”须并排显示双方依据并由用户采纳。原件失效时显示引用失效及历史摘要，不声称可以下载；是否使当前要求降为待核对及是否允许用户改为自身声明，需 B/C 在 RF-012 明确，不能篡改原确认历史。

#### 来源与老师任务的确认路径

1. 复用 RF-013 的授权来源读取和 Document/原行；本机用户声明保留明确 user_input 性质。样例 source/line ID 不是正式 EvidenceRef，不填进现有 evidence_ids。
2. 老师要求/任务先成为候选，用户明确选择目标课程及内容。课程详情只是可修改的上下文，不能把两课程＋普通事务全部默认写进当前课。
3. 通知 Case 路径继续复用 RF-016 与已有 Review 确认，候选 source_ref 经 owner、文档行和版本校验才映射为各 Case 的 Evidence；确认课程归属不等于确认行动或资格。
4. 无 Case 的课程任务由 D 的 RF-038/039 能力提供。C 建议单独确认老师原句及用户决定，由 D/C 共同确定同一 Evidence 模型如何绑定目标 task_id；在该协议未通过前不借用其他 Task/Case 的 Evidence、不创建假 Case、不把 source_ref 直接传入现有 Task API。
5. 来源/原件无效、老师要求不明和资格 UNKNOWN 分开提示；用户选择时间安排不能把 UNKNOWN 改为 TRUE。Task 截止、上课时间与执行日程分别管理，修改要求仅提示受影响任务/草案，不静默改时间。

#### 操作矩阵与混合执行边界

| 操作 | 确认前/取消 | 确认后的建议边界 | 版本、失败与消费者 |
|---|---|---|---|
| 新建/编辑课程、要求 | 页面编辑保留内存草稿，取消零正式写入；默认不调用 AI | 用户核对后按 RF-012 已确认保存策略提交；人工修改保留历史 | C 实现；stale 保留输入，跨 owner 拒绝；正式保存待 B/A/B 确认 |
| 混合导入/归属纠错 | 逐项选新增、更新、关联或忽略；有冲突另行核对；未选项不执行 | C 协调候选确认，Case 复用 RF-016，Task/资料委托 D/B；实际可用能力未就绪即显示待接入 | 保留操作标识、输入/目标期望版本及每项回执；具体 DTO/错误值待 Q10 |
| 确认与重试 | 没有执行回执不能报成功；取消不建 Case/Task/资料关系 | 独立操作分别执行；依赖项仅在前置真实成功且返回有效目标后执行 | 同键同内容复用成功结果，异内容冲突；成功项不重复执行，不覆盖后续人工值。传输超时先查回执；无查询能力记结果未知，不盲目重发 |
| 共享资料更新/解除 | 展示影响、版本及授权范围；取消不改原件 | B 执行关联/范围检索；课程解绑不级联删除共享原件，旧引用失效可见 | B 确认引用有效性；C 的 RF-050 不重复实现 B 课程关联 |
| 删除课程 | 先逐项展示要求历史、Task、时间规则、日程/提醒、资料关联影响 | 按用户选择委托 B/D；不能承诺本机/服务端统一事务。Task/日程默认不自动删除 | 保留每项已执行/失败/未执行结果；失败后不展示“全部删除成功”。恢复/补偿细节待 Q05/Q10 |
| 导出/恢复课程备份 | 告知包含档案/要求历史/规则/引用，不含服务端文件原件；恢复先预览 | 用户按明确课程范围选择合并或覆盖，不影响其他课程、画像或服务端原件 | 同名跨学期不合并；旧版/损坏/跨 owner 拒绝或按另审方案处理；离线引用待核对。具体范围/写入待 RF-012 |

操作标识建议沿用 RF-014～018 的同一机制，使用“候选身份＋操作版本＋具体目标”区分独立子项；更改归属/内容是新决策，不复用旧成功回执。具体键、摘要、保留期及回执查询接口仍须共同评审。**单项内部维持原事务原子性**，不得将混合输入的部分成功语义套到 S21 排程提交；排程中途失败仍整份回滚且可重试。

#### 样例与共同评审清单

合成输入及预期见 [JSON 样例](evidence/C_20261110/cm001_samples.json)，均未执行新契约：

| 样例 | 可复用内容 | 最少验证目标/对应决策 |
|---|---|---|
| C-CM-01 | 秋/春两门“线性代数” | 不误合并；Q01/Q08-d |
| C-CM-02 | 同一课程周一/周三两规则 | 两规则均保留；双来源同次占用不得重复计；Q04/Q08-d |
| C-CM-03 | 同一来源两课程作业＋摄影活动＋共享资料 | 逐项归属、更正/忽略、取消零写入；Q01/Q02/Q10 |
| C-CM-04 | 已确认闭卷与新开卷建议，另有要求四态 | 原句可追溯、不覆盖人工值、未知不变无要求；Q02/Q10 |
| C-CM-05 | 资料同时关联两课，删除其中一课后取消 | 展示影响、共享原件保留；Q05/Q10 |
| C-CM-06 | 旧备份、离线引用、其他 owner | 先预览冲突/失效，不自动覆盖/转移权限；Q05/Q08-d/Q10 |
| C-CM-07 | 独立执行项部分失败、断网后重试 | 失败可单独重试、成功不重复、依赖等待、单项原子；Q01/Q02/Q10 |
| C-CM-08 | owner 不符、stale、来源行不符、同键异内容 | 拒绝零写入且不泄露其他用户资料；Q01/Q02/Q10 |

评审时仍需把每种写操作的正常成功、拒权、stale、同键同内容、异内容、取消和注入失败回滚细化为具体请求/响应；本轮样例是输入和目标预期，不是这些接口已经通过的报告。

需要用户转达的具体确认（尚未发送团队消息）：

- **D：**确认课程/学期/规则身份分离，补规则发生映射与双来源去重；确认首切片 Task 课程关联基数及无 Case 老师任务的依据绑定/创建路径，沿 Q01/Q02/Q04/Q08-d/Q10 收口。
- **B：**确认本机课程档案/要求历史与 RF-012 的 owner/revision、退出、备份/恢复范围；确认资料多课关联及引用可见性。样例中 Document 只是引用，不证明原件已缓存。
- **A/B：**协调公共关系/权限/迁移及 RF-015 与 RF-038/039 顺序；确认旧课表逐条兼容/人工合并方案的范围，不以本节代签。
- **C 后续：**据实际反馈更新本条记录，由 D 回写唯一决策表；CM-002 固定样例页面可先消费这些合成输入，但正式保存、混合执行和 CM-003 跨模块恢复仍等对应确认。

### 4. 遇到的问题及解决

- 旧 Course 是单条时段记录，不能直接把两个同名条目合并成课程。保留兼容与显式确认建议，未修改旧存储或发生时段 ID。
- 文档中的“未合并/三项缺口开放”是历史状态：当前基线已含 B/C 成果及 D 的三项排程修复、固定网格；本轮提案依最新代码，不重复开发。不将 D 局部用户确认扩大为团队协议签认。

### 5. 测试与验证

- 本轮仅有文档和合成 JSON，未执行新契约/课程业务、真实迁移、前端构建、浏览器、Android、在线模型或跨模块执行测试。
- **未执行测试。**本次未新增或运行产品功能测试；以下仅为文档/合成数据检查，不能证明推荐协议的执行行为。
- 用 `python -X utf8 -` 从标准输入运行只读 JSON 检查（完整命令在本次会话）：20个对象 ID 唯一，学期/课程 owner 一致，规则/要求/建议的课程引用存在，来源行真实包含所引原句，四种状态齐全，8组场景的输入引用存在，退出0。不向生产服务发请求，不产生业务回执。
- `python scripts/check-docs.py`：206个本地 Markdown 链接/图片目标存在，退出0；未访问外部 URL。
- `python scripts/check-paths.py`：活跃源码未出现工作站盘符/用户路径，退出0。
- `node scripts/check-demo.mjs`：8份现有离线样例副本一致，退出0；不是浏览器或 APK 验收。
- `git diff --check` 退出0；新增 JSON 另经上述解析/引用检查，人工阅读其实际内容。最终改动限于本条记录与合成 JSON，未新增生产依赖。

### 6. 运行证据

- 本分支实际 diff、本条关系/操作矩阵及 JSON 合成输入；检查命令和输出在本次 Codex 会话。未生成 APK、截图、接口回执或真实文件备份。
- commit/PR、团队讨论或签认链接：待补充。请成员 C 保存本次原始 Codex 会话分享链接或导出；工作记录不能替代原始会话证据。

### 7. 未完成与限制

- 未实现 CM-002 页面、课程持久化/备份恢复、混合候选执行、独立 Task、知识多课关联或网格真实数据接入。本轮交付性质为 CM-001 的 C 侧设计与样例准备。
- CM-001 整卡需要相关成员按同一版本确认关系/操作及错误样例；确认前不进入高风险公共改动。本轮未更新 D/B 文件，也未修改三份团队计划或既有验收标准。
- 下一切片为 CM-002 档案/要求固定样例与编辑交互；先使用模块内展示模型，不接正式存储，不将其视为批准接口。正式导航若需改 `router.ts` 等公共文件，先声明范围并协调；不得为了页面可达提前迁移。

## RF-013｜导入恢复与 C/B 来源移交准备（2026-11-09）

### 1. 任务信息

- 负责人 C；目标是明确已保存批次到 B 填表 1C 的读取边界，并验证可复用的现有 API。
- 基线 `ce597a1`；实际分支 `docs/RF-013-source-handoff`。状态：接口提案与前置集成验证完成，待 B 对齐及 A/B 公共审查；RF-013 整卡未完成。
- 本轮编写及验证时尚未提交、推送或创建 PR；随后用户明确授权提交并推送此任务分支，实际提交与远端状态以 Git 历史为准。旧交叉评审 PR #6 在核对时仍开放，不把它的内容复制到本任务分支或当成公共签认。

### 2. 技术实现

- 新增 [C_RF013_source_handoff.md](C_RF013_source_handoff.md)：记录现有批次/Document 读取能力、旧粘贴正文缺口、最小只读接口提案、版本/权限/恢复语义及 H01–H08 验收矩阵。
- 新增 [test_notice_handoff_baseline.py](../../../server/tests/test_notice_handoff_baseline.py)：3 项集成测试覆盖同名附件身份隔离、失败来源替换保留原件、元数据存在但原件丢失。
- 没有修改生产业务代码、公共 DTO、数据库、Provider、B 页面或 Android 配置，没有实现 form-context API。

### 3. 设计与关键决策

- 先复用当前 Document 元数据、行与原件鉴权读取。建议单独只读 form-context 提供账户来源，避免直接扩展旧批次响应；URL/DTO 未获团队确认。
- 来源无独立 revision，不编造该字段；建议使用 batch revision、source_id、内容 hash，并保留 Document revision/hash。
- 旧粘贴正文没有 Document 行映射，不将填表显示行号当 Evidence。附件用途与模板版本由 B 的指纹校验和用户确认负责。
- 正式 API 变更待用户转达团队确认；RF-011 引用/删除保护和 RF-012 草稿边界仍保留依赖，不先迁移。

### 4. 遇到的问题及解决

- `git fetch origin --prune` 因 127.0.0.1 代理连接失败；使用 GitHub 只读工具核对最新提交仍为 ce597a1，PR #6 开放且讨论列表为空。未修改代理配置。
- 首次沙箱 pytest 无输出，已中止（退出1，无测试结论）；正常本机权限重跑后通过。未为获得通过删除断言或跳过用例。
- 编写阶段发现测试账户返回的 owner ID 位于 user.id，运行前修正临时文件定位；未改生产逻辑。

### 5. 测试与验证

环境：Windows PowerShell，已有 `.runtime/c-venv`（CPython 3.12.14）。内存数据库、合成账户与 TXT 字节；conftest 使用独立临时文件根并禁用在线模型。

```powershell
$env:TEMP=(Resolve-Path .runtime/c-rf013/tmp).Path
$env:TMP=$env:TEMP
.runtime/c-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_notice_handoff_baseline.py server/tests/test_document_api.py server/tests/test_link_candidates.py server/tests/test_analysis_retry.py -q -p no:cacheprovider
```

正常本机权限运行：**12 passed，5 warnings，2.53s，退出0**。其中新增3项、原有9项；警告为 FastAPI/Starlette/AnyIO 弃用。H01–H03 针对现有接口，不能证明新移交接口或 Office 填写通过。未执行全量后端、前端/浏览器、真实 OCR/网页/模型、真旧库升级或 Android 真机；本轮无 APK。

其他检查：`scripts/check-docs.py` 通过（149 个本地链接/图片引用）；`git diff --check` 通过。`scripts/check-api-contract.py` 沙箱首次指纹匹配但临时目录清理报 WinError5、退出1；正常本机权限重跑通过、退出0，仍匹配既有指纹 `aa40e470df16fa9b2143aa452c92dab9debaa18467e3b9a7694cbeb95df838ed`，未更新基准。

### 6. 运行证据

- 新增测试源文件及本次 Codex 命令输出；未生成共享日志或截图，不编造证据路径。
- 远端参考：[PR #5](https://github.com/Hanxx1/RuleFlow/pull/5)（B 分支 62ec31a）、[PR #6](https://github.com/Hanxx1/RuleFlow/pull/6)；不是本轮新增功能证据。
- 本任务实际 commit 见本文件所在任务分支的 Git 历史；本轮未创建 PR。原始 Codex 会话分享链接或导出待成员 C 保存。

### 7. 未完成与限制

- 待 B 确认正文/附件读取 DTO、legacy_text 消费及共同样例；待 A/B 审只读接口、用途授权及文件/草稿边界，确认后再实现。
- H04–H08 未执行，真实同通知多份原表及真机仍待样本/设备。未宣称 HTML 登录页识别、自动重试、移交 UI 或正式草稿已经完成。
- RF-002/003 最终签认与 RF-015/038/039 迁移顺序仍待团队决定；D 排程缺口不在本轮修复。

仅记录真实工作。首轮成果已于 2026-11-05 提交并推送（`786815c`），对应 [PR #2](https://github.com/Hanxx1/RuleFlow/pull/2)，2026-11-06 核对仍为 open、未合并。本次补测记录随同一分支提交，具体版本见 Git 历史。重要原始 Codex 会话分享链接或导出归档待 C 保存，本记录不能替代原始会话证据。

## RF-001｜C 模块走读子项

### 1. 任务信息

- 负责人：C；A 组织 RF-001 整体。日期：2026-11-05。
- 目标：明确导入→证据→Review→Task 的模块入口、运行方式与公共边界。
- 基线：`ac9e07c`；分支：`docs/RF-002-case-contract`。状态：C 侧走读、服务层验证和 2026-11-06 后端/API 补测完成；Web 启动未验证，团队 RF-001 不标完成。

### 2. 技术实现

- 走读 `features/imports`、`AnalysisResultView.vue`、`AnalysisReviewPanel.vue`、`services/review.ts`、`main.py` 的批次/旧导入/确认/附件/资源接口、`documents.py`、`review.py`、bootstrap/migrations 及相关测试。
- 请求链与数据关系并入 [RF-002 契约提案](C_RF002_contract.md)，避免重复写走读报告；没有修改正式业务代码。
- 建立忽略目录 `.runtime/c-venv` 和 `.runtime/c-first-batch`；找到了本机 bundled Python 3.12.14，Node v24.20.0；前端无 node_modules，未安装前端依赖。

### 3. 设计与关键决策

- 复用现有 Case、Document、Evidence、Review、Task，区分网页附件候选、行动步骤候选和待设计的候选事项。
- 第一轮仅文档/样例/实验，不改共享接口、迁移、公共 AI 或 Android 配置；分支从 fetch 后的 origin/main 创建。

### 4. 遇到的问题及解决

- PATH 无 python/py/uv；通过应用依赖定位工具找到 bundled Python，建项目内隔离 venv。
- 缺 pytest/FastAPI/httpx 等；安装先受 WinError10013 网络限制，网络放行后仍遇 PyPI TLS UNEXPECTED_EOF，未完成安装。pip 最后给出 ResolutionImpossible，但上游获取失败，不能认定是实际版本冲突；没有关闭 TLS 或修改 lockfile。
- 改用 stdlib unittest 直接运行生产纯服务模块，保留 API/运行环境阻塞。此方式不代替 FastAPI 集成测试。
- 2026-11-06：显式使用系统已配置的本机代理，默认 pip 解析仍在分离元数据请求时遇 TLS EOF；使用兼容解析器后按原 requirements/lock 安装成功，保留 TLS 校验。后续 `pip check` 无依赖冲突。

### 5. 测试与验证

- `git fetch origin --prune` 成功，origin/main 仍为 ac9e07c；读取 D 分支 d159808 的公共问题表，没有导入 D 的文档或修改其文件。
- 2026-11-05 未启动成功；2026-11-06 已通过现有脚本启动真实后端并完成 HTTP 健康、注册、验证、登录和事项往返，脚本结束后停止服务。29 项定向测试通过；具体命令与边界见 RF-002 补测记录。未执行 Web、浏览器、真机或在线模型测试。

### 6. 运行证据

- 请求链路径见契约；实验脚本见下；本机运行日志在忽略目录 `.runtime/c-first-batch/`，不是团队可直接访问的共享链接。
- 首轮成果 commit `786815c`、PR #2；本次启动证据为脚本输出，未拍截图。原始会话分享/导出：待补充。

### 7. 未完成与限制

- 后端依赖安装和 API 基线验证已补齐；Web 与团队 RF-001 共同样例口径尚未验收。Android 构建及分享验收依赖 A 的 RF-006。

## RF-002｜来源、候选事项与 Case 兼容契约

### 1. 任务信息

- 负责人：C；D 共审 Task/Evidence，A/B 审公共关系。日期：2026-11-05；基线/分支同上。
- 目标：说明现有关系、候选确认前后引用、旧数据兼容和依赖，给出可评审样例。
- 状态：C 侧提案与实验已有阶段成果，2026-11-06 已补后端/API 验证，待 RF-001 共同口径及 D/A/B 确认；整卡未完成。首轮成果 `786815c`、PR #2；本次补测文档在同一分支更新。

### 2. 技术实现

- 新增 `C_RF002_contract.md`：现有/建议关系图、实体基数、最小字段、六类场景、授权/版本/幂等/事务、旧数据与消费者影响、D Q01–Q10 的 C 侧建议及后续依赖。
- 新增 [probe_contract.py](evidence/C_20261105/probe_contract.py)：stdlib unittest，直接调用现有 bind_document、Review 服务和既有 apply_migrations。使用 AST 读取受控仓库 auth/bootstrap 中各唯一静态 SQL 字面量以建立内存 schema，不导入 API、不执行 AST 代码；foreign_keys=ON、合成账户/行、无文件原件或网络。
- 没有实现多候选 API、没有修改生产 schema/迁移；在测试内存库重放既有迁移不等于真实旧库升级验证。

### 3. 设计与关键决策

- 候选确认前用 source_ref，之后映射为 Case 范围 Evidence；同原件可共享，Evidence 不跨 Case 直接复用。
- 保留旧 ID、状态和 Review 门禁。建议事项选择和行动确认分阶段；最终交互、字段、URL、迁移顺序尚待审。
- 公共决策继续以 D 的唯一表为准，本提案只提供 C 意见；没有代替成员签认或对外发送消息。

### 4. 遇到的问题及解决

- 实验复现 case_attachment_documents 的 document_id 主键限制；绑定第二 Case 触发 IntegrityError。文档标为待设计共享关联，未修业务表。
- 首次探针：7 项成功、1 项实验错误，因自写 legacy Task fixture 的 INSERT 多一个占位符；改为10个后8项通过，生产代码未改。首次日志保留。
- 批次只有单 case_id，纯文本无 Document 行、旧单 evidence_id 无法表达多行映射；已列兼容与后续实现边界，未提前迁移。
- 补测遇 Windows 沙箱临时目录无法创建/清理，29项首次均在 fixture 准备阶段出错；改 TEMP/TMP 后沙箱运行仍无进度，已中止。真实启动首试健康检查超时且临时目录清理报 WinError5。使用项目忽略目录作临时目录，在正常本机权限下运行原测试/启动脚本后通过；未改测试断言或生产代码，未判定为业务缺陷。

### 5. 测试与验证

实际环境：Windows PowerShell；bundled CPython 3.12.14；SQLite 内存；无线上服务、模型或真实个人资料。项目 README 的原验证环境为 Python3.11，本次结果不外推为完整安装兼容。

```powershell
# 仓库根，使用实际存在的本地环境
& .runtime/c-venv/Scripts/python.exe -X utf8 docs/development/records/evidence/C_20261105/probe_contract.py
```

最终 **8 tests，OK，退出0**：同原件跨Case绑定/幂等、文档与Case owner校验、Review门禁/重复确认、stale拒绝、同owner跨Case证据拒绝、旧Task ID及done状态保留、附件共享主键限制复现、既有迁移重放不变。限制复现通过代表观察符合现状，不代表共享附件功能已实现。

测试依赖安装实际尝试：bundled Python `-m venv --system-site-packages .runtime/c-venv` 成功；随后 `.runtime/c-venv/Scripts/python.exe -m pip install -c server/requirements.lock fastapi uvicorn python-multipart httpx beautifulsoup4 pytest argon2-cffi email-validator tzdata` 失败（网络权限；重试含 `--retries 0 --timeout 20` 后 TLS EOF）。未改依赖声明，未完成后端环境安装。

其余实际检查：

```powershell
& .runtime/c-venv/Scripts/python.exe -m pytest server/tests/test_review_api.py server/tests/test_review_service.py server/tests/test_document_api.py server/tests/test_link_candidates.py -q -p no:cacheprovider
& .runtime/c-venv/Scripts/python.exe -m uvicorn app.main:app --app-dir server --host 127.0.0.1 --port 18002
& .runtime/c-venv/Scripts/python.exe scripts/check-docs.py
git diff --check
```

- pytest 入口退出1：`No module named pytest`，用例未收集/执行；API 测试未执行。
- uvicorn 入口退出1：`No module named uvicorn`，服务未启动，未监听端口。
- 文档检查退出0：PASS 123 local Markdown link/image targets；只核对本地链接，不含外链/远端内容。Git 提示用户配置目录 ignore 无访问权限，但检查本身通过。
- `git diff --check` 退出0；新文件尚未跟踪，此命令不能替代对新增文件的检查。
- 多候选样例仅设计，未实际运行新接口；没有全量回归、并发、Android/浏览器、真实旧库迁移或在线模型测试结果。

#### 2026-11-06 后端/API 补测

以下结果更新先前“缺少 pytest/uvicorn”的环境阻塞；保留上面的首次失败历史。验证源码仍为 `786815c`（业务基线 ac9e07c），没有新增正式功能。

实际安装命令（仓库根、仅项目 venv）：

```powershell
& .runtime/c-venv/Scripts/python.exe -m pip install --proxy http://127.0.0.1:10808 --use-deprecated=legacy-resolver --retries 1 --timeout 20 --disable-pip-version-check -r server/requirements.txt -c server/requirements.lock
& .runtime/c-venv/Scripts/python.exe -m pip check
```

安装退出0；`pip check` 退出0，`No broken requirements found`。代理地址是本机当前配置，不是团队通用前提；未修改系统设置、TLS、requirements/lock。环境沿用 `--system-site-packages` 的 CPython3.12.14 venv，部分满足约束的库来自 bundled runtime；这不是 README Python3.11 干净安装复现，也不宣称环境完全独立。

实际验证命令（先创建 `.runtime/c-validation-20261106/tmp`，下列环境变量仅作用于本次进程；最终 pytest/smoke 使用正常本机权限）：

```powershell
$env:TEMP=(Resolve-Path .runtime/c-validation-20261106/tmp).Path
$env:TMP=$env:TEMP
& .runtime/c-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_review_api.py server/tests/test_review_service.py server/tests/test_document_api.py server/tests/test_link_candidates.py server/tests/test_analysis_retry.py server/tests/test_api.py::test_health_endpoint server/tests/test_api.py::test_import_batch_schema_migration_is_applied server/tests/test_api.py::test_task_material_and_edge_reject_cross_case_references server/tests/test_api.py::test_import_batch_persists_mixed_sources_traces_evidence_and_is_idempotent server/tests/test_api.py::test_import_batch_partial_failure_failed_and_failed_source_recovery -q -p no:cacheprovider
& .runtime/c-venv/Scripts/python.exe -X utf8 scripts/smoke-startup.py
& .runtime/c-venv/Scripts/python.exe -X utf8 scripts/check-api-contract.py
```

| 检查 | 输入/预期 | 实际结果 |
|---|---|---|
| 定向 pytest | 合成账户/通知/文件，内存 SQLite；确认门禁、UNKNOWN、依赖、stale/幂等、旧 Task 保留、事务回滚、owner/跨Case拒绝、附件授权、失败恢复及批次多来源 | **29 passed，5 warnings，3.49s，退出0**；不是全量回归 |
| 真实 HTTP 启动 | 随机本机端口、独立临时库；健康→注册→验证→登录→新建/读取事项，从非仓库 cwd 启动 | PASS，退出0；进程由脚本在 finally 中终止，不保持服务运行 |
| OpenAPI 基准 | 指纹与已接受基准一致 | PASS，退出0，`aa40e470df16fa9b2143aa452c92dab9debaa18467e3b9a7694cbeb95df838ed`；未重写基准 |

5条警告来自 Starlette/httpx、AnyIO BlockingPortal 和 FastAPI on_event 弃用，未为消除警告改公共依赖。API 用例使用 TestClient；网页获取和 OCR 等部分由现有用例替身隔离，不代表公网下载、真实 OCR 或模型效果通过。真实 TCP HTTP 检查仅覆盖表中启动链，不冒充完整通知业务的真机闭环。

当前仍未执行前端测试/构建、Web 浏览器交互、Android、在线LLM、真实旧库升级、新候选API与并发确认验收。29项通过不能视为 RF-002 契约已批准或整卡完成。

### 6. 运行证据

- 本分支中的契约与探针；本地日志 `.runtime/c-first-batch/probe.txt`（最终8项通过）、`probe-first-attempt.txt`（首次fixture错误）、`api-tests.txt`、`startup.txt`（入口缺依赖）、`docs.txt`（文档检查通过）。日志未提交、其他成员可用脚本复现。
- 参考的 D 交付：[PR #1](https://github.com/Hanxx1/RuleFlow/pull/1)，核对版本 d159808；不是 C 的实现/测试证据。
- 补测日志本机位置：`.runtime/c-validation-20261106/install.txt`（默认解析失败）、`install-legacy-resolver.txt`（安装成功）、`pip-check.txt`、`api-tests.txt`（沙箱fixture失败）、`api-tests-workspace-temp.txt`（中止，无完成结论）、`api-tests-local.txt`（29 passed）、`startup.txt`（首试失败）、`startup-local.txt`（HTTP通过）、`api-contract.txt`。这些日志位于忽略目录，未提交，不是公开共享证据。
- C 首轮成果 `786815c`、[PR #2](https://github.com/Hanxx1/RuleFlow/pull/2)；共同签认、截图和原始 Codex 会话分享/导出：待补充。本次原测试/脚本已在仓库中，其他成员可按命令复现。

### 7. 未完成与限制

- RF-001 样例口径；D Q01/Q02 的 Evidence/独立Task、Q03 skipped、Q05 删除引用；B 文件与草稿/资料边界；A/B 对交互和迁移顺序的确认。
- 待团队评审才能定稿或进入依赖公共契约的正式功能；现在仍可完善独立走读/样例。RF-014/015/016/017、020/021、独立Task及共享附件功能均未在本轮实现。
- 公共文件修改须先沟通；首轮成果已推送并发起PR，本次获用户授权将补测文档提交至同一远端任务分支，保持待评审状态，不合并主分支。

#### 2026-11-09 C 侧交叉评审补记

在 `docs/RF-002-contract-review` 分支（基线 `ce597a1`）完成 PR #3 的五项 C 侧审阅，逐项意见、给 D 的依赖样例及与 B 的来源移交提议见 [C 契约第 9 节](C_RF002_contract.md)。本轮改动限于两份 C 文档。RF-015 迁移顺序待 A/B 与 C/D 确认，公共决定由 D 回写。

从仓库根运行以下命令。首次沙箱运行在 pytest 临时目录创建阶段遇到 24 个 fixture 错误，以正常本机权限重跑同一命令，**24 passed，5 warnings，5.27s**。覆盖新增 10 项与既有 14 项，警告来自 FastAPI/Starlette 测试及生命周期接口。使用隔离内存库和合成账户。本轮未运行全量回归或三个已知缺口的探针。证据为本次命令输出及 [边界测试源文件](../../../server/tests/test_schedule_boundaries.py)，原始会话归档待补充。

```powershell
.runtime/c-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider
```
