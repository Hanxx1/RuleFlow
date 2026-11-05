# 有绪 CampusWeave｜D 个人日程与智能排程工作记录

仅由成员 D 维护。每个 RF 任务一条主要记录，后续补测/评审更新原条目。当前不编写复赛正式报告。

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
- 状态：准备子项已有可评审成果；待争议预期确认。RF-043整卡约束修复未开始，不标已完成。

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
