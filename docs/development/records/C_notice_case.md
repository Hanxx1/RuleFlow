# 有绪 CampusWeave｜成员 C 开发工作记录

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
