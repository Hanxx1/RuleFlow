# 有绪 CampusWeave｜D 个人日程与智能排程工作记录

仅由成员 D 维护。每个 RF 任务一条主要记录，后续补测/评审更新原条目。当前不编写复赛正式报告。

当前状态（2026-11-10）：用户授权将本阶段成果作一次本地提交，不推送；成果版本以包含本段的提交为准。RF-043三项后端与页面恢复修复、CM-005固定样例日/周网格已完成本地切片；RF-003/CM-001决策表及RF-007环境/提醒方案已整理。提交前重跑后端全量223项、前端114项通过，类型检查与生产构建通过。既有移动尺寸浏览器和真实API恢复证据见各专题记录，本轮未重跑浏览器链。模拟器与原生提醒验证留待后续，RF-007未实现，整卡/真机未验收，无APK。本机SDK配置、临时数据与测试产物不提交。下方“未提交”均为历史阶段状态，以本段为准。详见 [RF-043收口检查](D_RF043_closeout.md)、[CM-005方案](D_CM005_grid_proposal.md)、[RF-007方案](D_RF007_reminder_proposal.md)。

## RF-001｜D 的 Task → 排程草案工程走读

### 1. 任务信息

- 负责人 D；日期 2026-11-05；目标：说明自己模块的请求链、数据、消费者和未知项。
- 状态：D 侧源码走读、后端定向测试和真实HTTP启动完成；已补 Chrome headless 移动尺寸页面登录、任务、草案与确认交互；人工浏览器/真机未验，A组织的四人整体RF-001未验收。
- 基线 `ac9e07c`，初始在 `main`（流程不足已纠正），现为独立工作区分支 `docs/RF-003-RF-043-prep`；开始时工作区干净。本轮为文档和隔离实验，按用户要求在当前任务分支提交并推送；实际成果commit以本文件所在分支Git历史为准，未创建PR。基线commit不代表本轮成果commit。

### 2. 技术实现

- 请求链、入口/函数/消费者见 [RF-003契约第1节](D_RF003_contract.md)。实际新增本记录、契约、公共待确认清单、RF-043样例及 evidence/D_20261105 中的实验脚本；原始日志已移到忽略目录 `.runtime/d-first-batch/evidence`，不加入提交。
- 复用现有 TestClient 合成账户辅助函数、pytest 隔离机制和 smoke-startup 脚本；没有修改正式业务源码、前端、依赖、配置或迁移。

### 3. 设计与关键决策

- 区分任务状态、正式日程和不可变草案；区分源码事实、建议契约和未确认团队决定。
- 只维护D记录，不修改其他成员记录；使用新品牌命名新增资料，不全局替换旧名称。

### 4. 遇到的问题及解决

- 默认执行工具启动失败；获工具许可后使用直接执行完成读写和验证。桌面浏览器工具连续两次初始化失败，改用本机已有Chrome无界面集成实验。第一次Web脚本同步点击确认被原生弹窗阻塞超时；修正实验脚本为异步点击并处理弹窗后通过，应用源码未改。
- README的server/.venv不存在；改用已有.runtime/review-venv，Python3.11.6，未安装或升级依赖。
- 最初猜测的 `mobile/src/stores/cases.ts`、`server/tests/test_product.py` 不存在；通过rg定位真实cases store及排程专项测试，没有创建替代文件。

### 5. 测试与验证

- 实际命令见 [RF-043样例的运行部分](D_RF043_cases.md)。五个排程/课表测试文件共14项通过，5项warnings。
- `& .runtime/review-venv/Scripts/python.exe scripts/smoke-startup.py`：退出0，真实HTTP健康、注册、验证、登录、事项往返PASS；数据为临时合成数据，过程自动停止服务。
- 已执行真实 Web 页面集成实验（Chrome headless，390×844），API 只用于合成数据准备与结果核对；通过页面登录、查看任务、预览、取消确认及确认提交。日程数依次为0→0→0→2，页面显示整份排程已保存。取消指关闭确认弹窗，不代表已实现取消草案API。未执行完整后端/前端测试、真机分享、APK构建或在线模型测试。
- 新工作区重新执行同一五文件基线：14 passed、5 warnings，退出0。
- Web命令：`python -X utf8 docs/development/records/evidence/D_20261105/web_check.py`；运行前将 `CAMPUSWEAVE_TEST_PYTHON` 指向已有后端Python环境。脚本宿主Python3.14需已有websocket-client；node/Vite与Chrome均使用本机已有安装，没有新增产品依赖。

### 6. 运行证据

- 新增本地 `.runtime/d-first-batch/web-results.json`、`web-run.txt`、`tasks.png`、`preview.png`、`confirmed.png`；截图仅合成数据，人工查看了提交成功截图。脚本已随记录保存；原始日志/截图/临时数据库/浏览器资料不提交。
- `本地证据：.runtime/d-first-batch/evidence/startup.txt`、`本地证据：.runtime/d-first-batch/evidence/pytest-scheduling.txt`、源码走读路径见契约。
- 原始Codex会话：当前聊天；可分享链接/导出归档待D保留。本工作记录不能替代原始会话证据。

### 7. 未完成与限制

- A仍需汇总RF-001共同样例及协作规则；人工浏览器和真机证据待补，自动化Web证据已补。没有本次APK产物。
- 已通过应用原生工具建立独立工作区及短期分支；本任务九个原文件逐个备份、哈希核对后从原main目录移除，原目录恢复干净。业务开发前仍需协调公共文件。

## RF-003｜Task、Schedule和证据共同契约

### 1. 任务信息

- 负责人D，C共拟、A/B审；日期2026-11-05；基线/分支同上，成果commit见当前分支Git历史，未创建PR。
- 目标：独立任务、通知任务、日程、分段、课程和提醒语义一致。状态：D提案已整理，待共同评审；不标整卡完成。

### 2. 技术实现

- 新增 [D_RF003_contract.md](D_RF003_contract.md) 和 [D_public_interface_questions.md](D_public_interface_questions.md)。包括实际请求链、现有字段/接口、操作前后状态矩阵、成功与错误样例、迁移影响和后续依赖。
- 核对main.py、schemas.py、bootstrap/migrations、api/planning.py、schedule/schedule_drafts/review、PlanView/PlanSchedule及cases store。只有设计与走读，没有修改正式功能。

### 3. 设计与关键决策

- 提议复用Task/Evidence，独立任务不使用假Case；通知Review门禁保留，owner隔离不放松。
- 不自动双向完成Task与时间片；正式占用和草案固定分开。以上推荐尚待确认，唯一公共决策表Q01–Q10不预填签认。

### 4. 遇到的问题及解决

- tasks/evidence强制Case，现有门禁/查询/排序存在Case假设；只放松DTO不够。已列消费者影响，未做迁移。
- 旧缺省task_ids与空数组都全选，当前页面依赖缺省行为；不能直接把空数组改成无选择破坏旧流程。
- 完成/跳过、时区、提醒版本等公共语义未决，以清单显式保留，不代替其他成员作决定。

### 5. 测试与验证

- 复用本轮14项定向测试和三项边界观察核对当前行为；命令和输出见RF-043条目。
- 未执行独立Task迁移、契约兼容测试计划或新增状态联动测试；设计未视为实现通过。

### 6. 运行证据

- 本次契约、独立待确认清单及RF-043日志；源码基线ac9e07c。C/A/B评审结论、讨论链接和签认：待补充。

### 7. 未完成与限制

- RF-002的Evidence关系、RF-012的课表/授权边界需C/B提供；Q01–Q10全部未确认。
- 038/039迁移不得先行；本轮不选择迁移编号、新URL、原生插件或新的状态枚举。

## RF-043｜排程正确性样例准备子项

### 1. 任务信息

- 负责人D，C提供通知样例、A复核解释；日期2026-11-05；基线/分支同上。
- 状态（2026-11-09更新）：S03、S05/S06、S07后端修复及页面恢复切片已通过本地验证；最新全量后端223项、前端96项与移动恢复链见收口记录。其他争议语义、跨成员评审和真机验收仍开放，不标整卡完成。

### 2. 技术实现

- 新增 [21组样例矩阵](D_RF043_cases.md)，区分E现有测试、P缺口复现、N尚未运行。
- 新增隔离脚本 [probe_boundaries.py](evidence/D_20261105/probe_boundaries.py)，复用现有测试账户/通知确认辅助函数，内存SQLite、临时上传路径、无在线模型；仅输出当前行为，不将缺陷固化为验收断言。

### 3. 设计与关键决策

- 先确定预览/提交共同约束，之后才改求解器；任务排序分数不是多方案质量分数。
- 使用纯合成样例复现外部前置不足、过去时间和UTC纯日期截止，保留失败前后的日程数量；不使用真实资料。

### 4. 遇到的问题及解决

- 三个业务缺口已复现：选集外90分钟前置只安排30分钟仍给后置建议，提交409；2000年时间草案可提交200；UTC预览17:00可行但提交按Asia/Shanghai解释纯日期而409。均未修复。
- 第一次探针使用磁盘SQLite，输出观察后临时目录清理报WinError32；参考现有测试，改为内存库并显式关闭连接，重跑退出0。用 `-X utf8` 解决最终日志中文编码；首次日志保留，不掩盖失败。

### 5. 测试与验证

实际执行：

```powershell
& .runtime/review-venv/Scripts/python.exe -m pytest server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings
& .runtime/review-venv/Scripts/python.exe -X utf8 docs/development/records/evidence/D_20261105/probe_boundaries.py
```

- 14 passed，5 warnings，pytest退出0；覆盖既有草案、拆分、偏好、锁与课表，不是全量回归。
- 最终探针退出0，三项业务目标均暴露缺口；拒绝两例日程数量1→1及0→0，过去时间例0→1。不将“脚本正常退出”表述为功能通过。
- 矩阵N项未执行；S06自然过时、S21中途失败回滚等尚需定向用例，不用已有测试名代替证据。

### 6. 运行证据

- `本地证据：.runtime/d-first-batch/evidence/pytest-scheduling.txt`、`本地证据：.runtime/d-first-batch/evidence/boundary-results.txt`、`本地证据：.runtime/d-first-batch/evidence/boundary-first-attempt.txt`、实验脚本与测试矩阵。
- 无截图/录屏/APK；原始Codex会话分享或导出待D保存；成果commit见当前分支Git历史，未创建PR。

### 7. 未完成与限制

- Q03/Q06/Q07/Q08待确认；C的真实去标识通知依赖样例、B的课表版本口径待补。
- 未实现043约束修复、044多候选评分、045–047编辑重算、048提醒；RF-007设备验证仍依赖A的RF-006。
- 首次失败的临时磁盘目录可能残留；未删除不明路径。后续最终实验使用内存库且正常退出。

## 2026-11-08 RF-043 第二批边界验证

用户授权补跑S01/S04/S20/S21；基线main `4f9b266`。新增 `server/tests/test_schedule_boundaries.py` 共10项，覆盖精确单任务预览、选集外前置足量/缺失、时间窗口拒绝与14天默认窗口、第二片失败的事务回滚和同草案重试。新增及既有排程定向测试24 passed、5 warnings、退出0。命令、实际结果和本地日志见 `D_RF043_cases.md` 的当日补充节。

本次无业务代码、API、迁移、UI或依赖变更，无APK；未全量回归或真机验收，未提交/推送。S03/S05/S07既有缺口仍开放；其余未运行样例和公共Q01–Q10决策不因本轮测试通过而关闭。下一步按契约确认情况补其他边界或进入定向缺陷修复。

## 2026-11-08 RF-003 与 C 的 RF-002 契约对齐

完成D侧对照审阅，方案写入 `D_RF003_contract.md` 第7节，唯一决策表 `D_public_interface_questions.md` 补Q01/Q02评审入口。收敛Task来源与Case分离、独立/跨Case依赖范围、task作用域用户Evidence、候选到Case引用映射、排程显式引用与受控解析、UNKNOWN消费和兼容验收清单。以main `4f9b266`的源码为事实，新增URL/字段/行为均标建议。

本轮仅文档，未实施API/迁移/业务代码、未向团队发送消息或代签确认；未重跑测试，无APK。本聊天此前新增10项测试及24 passed记录保留，不作为新契约验收。Q01/Q02及RF-003仍待C/A/B评审；下一步取得最小决策包反馈后协调公共迁移。

## 2026-11-09 RF-043 S03 定向回归与最小修复方案

- 范围：用户授权补前置任务耗时不足回归、定位预览/提交差异、整理方案；未授权本轮实施修复。
- 实现：新增6项参数化测试，四项预览目标和两项旧草案提交防线；生产代码、schema、迁移、UI、依赖均未改。
- 根因：预览只传选集外前置status，未传耗时；已有安排分支只看最晚结束，没有累计耗时门禁。提交按同owner查询耗时并检查累计分钟，正确拒绝。
- 验证：首次4 failed、2 passed；严格限定已知缺陷后与既有排程回归合跑26 passed、4 xfailed、5 warnings。失败位于预期的错误建议断言；两项提交保护均验证409、正式日程不变和草案pending/未提交。隔离内存数据库、合成账户、无在线模型。
- 方案与命令：[S03最小修复方案](../../superpowers/plans/2026-11-09-rf043-s03-predecessor-duration.md)。建议只增加内部耗时传递和外部前置足量判断，保留提交防线，按协作边界确认后实施。
- 限制：S03未修，xfail不计通过；全量/移动端/Android未测，无APK；未提交、推送或发送团队消息。


## 2026-11-09 RF-043 S03 局部修复（后续授权）

用户明确要求按最小方案修复并跑相关回归，暂不提交/推送。修改`api/planning.py`的owner限定耗时查询/传参及`services/schedule.py`的外部前置累计分钟判断；未改提交校验、API结构、数据库、依赖、UI或其他公共契约。

新增测试扩至18项并移除xfail。修复前15失败3通过；首次编辑漏定义durations造成NameError，补齐后相关排程42 passed、5 warnings。OpenAPI契约核验通过且基线不变。两项旧草案保护仍拒绝不合法提交且无状态损坏，完整90分钟及31分钟实际预览/提交通过。

计划的多片段边界通过纯算法验证；未跑全量后端、移动端或真机，无APK。S05/S07仍开放。具体命令、范围和实施记录见[S03方案](../../superpowers/plans/2026-11-09-rf043-s03-predecessor-duration.md)。全部变更保留本地未提交、未推送。


## 2026-11-09 RF-043 S05/S06 测试与定位

用户要求先补过去窗口和草案自然过时回归、定位及最小方案，暂不提交/推送。新增9项测试，生产文件保持上轮S03修复状态。

根因：API只在起点省略时使用now；草案snapshot不包含时间，提交now仅作时间戳，未检查片段是否已开始。冻结排程时钟且保持快照不变后，S06两例实际提交2条日程，不能由既有数据变更失效测试替代。

验证：首次6失败3通过，最终45 passed、6 strict xfailed、5 warnings；原S03相关42项仍通过。方案推荐预览明确拒绝显式过去起点、提交写入前检查所有片段，保留幂等；Q08和新错误码仍为提案。详见[最小方案与复现命令](../../superpowers/plans/2026-11-09-rf043-s05-s06-time-boundaries.md)。未全量/真机验证，无APK；所有改动未提交、未推送。


## 2026-11-09 S05/S06 拒绝策略实施

按用户明确授权实现：API显式过去起点422；草案提交在幂等/快照保护后、首条写入前比较全部片段，任一已开始则409 DRAFT_EXPIRED整份拒绝。保持手工历史日程语义、权限、consent、calendar_revision及事务保护。

时间用例扩至18项，RED为10失败8通过；修复后相关排程加review_api共66 passed、5 warnings、退出0，无xfail；OpenAPI指纹不变。新增局部排程时钟helper，旧drafts及一项splits HTTP测试保留原输入并冻结排程时钟。未来片段、相等时刻、微秒过时、晚到幂等、空草案、老草案以及过时片段在列表末尾的零写入均验证。

API文档和Q08局部用户选择已同步；不代签团队其他契约。S07未修，未全量或真机验收，无APK，未提交/推送。


## 2026-11-09 RF-043 S07 测试、定位与方案

用户只授权第三项回归/定位/最小方案，暂不提交或推送。新增11项截止时区测试，保留已有生产修复不动。两项实际预览与提交差异均为纯日期UTC解释比上海晚8小时；带明确offset标准化UTC的9项相关对照/边界通过。

实际初次2失败9通过；严格限定已知差异后与原66项合跑75 passed、2 xfailed、5 warnings。提交保护仍正确拒绝并保持日程及pending草案。方案拟统一排序、紧迫度和窗口计算与现有提交口径，不因请求timezone放宽截止；Q08纯日期规则尚未决定。见[S07方案](../../superpowers/plans/2026-11-09-rf043-s07-deadline-timezone.md)。未全量/真机验证，无APK，未提交/推送。


## 2026-11-09 S07 截止时区一致性实施

用户明确授权上海纯日期口径并要求不提交/推送。新增task_deadline helper，预览排序/紧迫度/窗口与提交统一调用；明确offset保留绝对时刻，工作时段仍跟随请求timezone。review已有上海语义不改。

S07测试21项、另加review服务精确边界2项；RED 7失败12通过，最终相关12文件99 passed、5 warnings、无xfail。OpenAPI结构指纹不变。API文档与Q08局部确认、矩阵均更新。全量/DST/旧库/浏览器/真机未验，无APK；全部保留本地未提交/推送。

## 2026-11-09 合入主线、集成回归与职责核对

- 用户授权把远端main合入当前修复分支，保留修改、不提交/推送。fix/RF-043-scheduling-consistency已由4144bdb快进到b40b631，合入PR #5共3提交/15文件，无冲突、无新合并提交。合并前后17个本地修改或未跟踪文件SHA256全部一致。
- 合并后后端相关12文件99 passed、5 warnings；前端首次因node_modules缺失已声明fflate导致2套测试无法加载，未误报功能失败。运行npm.cmd --prefix mobile ci --ignore-scripts恢复锁定依赖后，19个测试文件96 passed；vue-tsc与Vite生产构建通过。package.json/package-lock.json无差异。
- OpenAPI指纹保持既有基线；171处本地文档链接检查及git diff --check通过（当时计数）。未运行浏览器E2E、真机或APK构建；构建输出在mobile/web-dist。
- 依赖安装自动审计报告16项漏洞（9 moderate、4 high、3 critical）；未展开逐项归因，未执行audit fix或升级依赖，不能把单测/构建通过视作依赖安全验收。
- 职责依据：TEAM_EXECUTION_PLAN第2节及RF-043/044归属行为D；DEVELOPMENT_WORKLOAD_ASSESSMENT的RF-043明确列出显式过去时间、提交过时、时区、选集外前置耗时。因此本地三项修复属于D的硬约束/草案一致性职责。
- 本地生产修改仅planning.py、schedule.py、schedule_drafts.py；test_review_service.py仅加跨边界截止回归，未改C的review生产逻辑。API说明/Q08记录属于D的RF-003协调范围；合入的RF-028填表代码属于B既有远端成果，不计D实现，本次仅验证集成。
- 团队计划仍要求相关成员交叉评审、A组织集成验收及公共语义审阅。用户已明确授权本地切片与规则选择，但不是全体团队签认；未扩大到独立Task迁移、通知/填表新功能或其他未定契约。


## 2026-11-09 页面恢复修复与全量验证

按用户授权，仅增量修改PlanSchedule.vue：预览省略显式now起点；DRAFT_EXPIRED禁用旧确认并提供重新预览；网络失败保留同草案重试。新增独立真实API/390×844触控回归，先后观察422与过时确认可点击两处RED，再验证8项恢复行为GREEN。实际提交响应丢失后晚到重试返回幂等，日程两条ID不变。

后端全量223 passed、5 warnings；前端96 passed、类型检查与构建通过（Vite CJS弃用告警保留）。测试专用排程时钟、模拟传输失败、独立合成数据，无真实账户/物理设备；详细命令及证据见 [收口记录](D_RF043_closeout.md)。未提交/推送，无APK；不将局部修复视为RF-043整卡或团队签认。


## 2026-11-09 RF-003与CM-001的D侧决策整理

fetch后origin/main仍为d8672de；C最新契约评审为f34e70e第9节。唯一决策表已将Q01/Q02从“待C共审”更新为“C已接受核心语义、团队待确认”，区分Q08用户局部确认和课程产品方向；其余未决项按子项列责任、所需反馈与具体阻塞。CM-001的D输入纳入原Q编号，补课程/规则/Task/占用、截止、备份删除和混合执行矩阵及6组待验样例。

没有代签A/B/C、没有把C旧测试接受扩大到后续RF-043修复，也没有实施URL/Schema/迁移。详细现状仅见 [唯一公共决策表](D_public_interface_questions.md)；未提交/推送或向团队发送消息。本轮纯文档，未重复业务测试或生成APK。


## 2026-11-09 CM-005固定样例网格方案（未实施）

检查PlanView/PlanSchedule/ClientCalendarPanel及现有样式：当前是选日列表，非小时网格，且开始日过滤不能覆盖跨日；本机课表与账户数据流独立。推荐展示组件＋纯布局＋显式只读样例入口，日/周导航、上海时间轴、重叠分列、午夜裁剪与样例详情。具体建议及G01–G12移动验收见 [CM-005最小方案](D_CM005_grid_proposal.md)。用户尚未确认布局取舍，本轮仅方案，不写产品代码、接真实课程接口、提交或推送；新用例未执行，无APK。


## 2026-11-09 CM-005固定样例网格实施（最新）

按用户授权完成纯布局/只读日周网格/样例详情与PlanView显式入口，空账户和离线可达；不接真实课程接口，不改RF-043账户排程逻辑。15布局＋3依据渲染新增回归，前端全量114 passed、类型/生产构建通过；G01–G12由纯函数、渲染与390/360/横屏Chrome触控组合验证，RF-043真实恢复链8项通过。审查发现的依据未标待核对、最右时间轴漂移均有RED→GREEN修复。

详情、命令和本地截图入口见 [CM-005方案第8节](D_CM005_grid_proposal.md)。无物理设备/真实课程联调/CM-006同步去重验收，无APK；未提交/推送。原有非目标修改哈希检查保持，测试产物位于忽略的.runtime目录。


## 2026-11-09 RF-007提醒能力盘点（无实现）

源码未发现原生提醒插件/调度/取消/恢复；只有分享桥与Preferences。Java17可用，当前SDK环境变量/local.properties/PATH ADB未配置，常见目录未定位，设备连接授权与APK基线无法核实。已整理一条合成日程的调度、取消/改时、冷重开/设备重启、拒权/撤权、离线和节电等R01–R16矩阵，全部原生场景未测。官方文档核对及最小候选方案见 [RF-007盘点](D_RF007_reminder_proposal.md)；Q09仍待公共评审。

本轮仅文档和只读检查，不安装插件、不cap sync、不改权限/设备状态、不运行原生构建或业务测试。未提交/推送，无新APK；B文件子项不代验。


## 2026-11-09 RF-007环境复用配置（最新）

定位D:/Android/Sdk，ADB37.0.1可执行；用户级ANDROID_HOME与PATH已配置，项目忽略的local.properties已写sdk.dir，现有Resolve-Adb实际解析通过。android-36及Build Tools35/36已在机，项目compileSdk34平台仍缺，未下载/改版本/构建。ADB两次设备列表为空；用户选择本轮仅环境配置，真机连接授权未验。已有AppFunctions_API36_1模拟器仅列举，未启动。详见 [RF-007盘点第6节](D_RF007_reminder_proposal.md)。未新增插件、安装APK、提交或推送。
