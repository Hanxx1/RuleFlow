# 有绪 CampusWeave｜成员 C 开发工作记录

仅记录真实工作；当前成果未提交、未推送，未创建 C 的 PR。重要原始 Codex 会话分享链接或导出归档待 C 保存，本记录不能替代原始会话证据。

## RF-001｜C 模块走读子项

### 1. 任务信息

- 负责人：C；A 组织 RF-001 整体。日期：2026-11-05。
- 目标：明确导入→证据→Review→Task 的模块入口、运行方式与公共边界。
- 基线：`ac9e07c`；分支：`docs/RF-002-case-contract`。状态：C 侧走读和有限服务验证完成；后端/Web 启动未完成，团队 RF-001 不标完成。

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

### 5. 测试与验证

- `git fetch origin --prune` 成功，origin/main 仍为 ac9e07c；读取 D 分支 d159808 的公共问题表，没有导入 D 的文档或修改其文件。
- 后端 pytest 与启动尝试、服务层实验结果见 RF-002 同轮记录；没有实际启动 Web 或后端服务。未执行浏览器、真机或在线模型测试。

### 6. 运行证据

- 请求链路径见契约；实验脚本见下；本机运行日志在忽略目录 `.runtime/c-first-batch/`，不是团队可直接访问的共享链接。
- 分支已存在；成果 commit/PR、服务启动截图、原始会话分享/导出：待补充。

### 7. 未完成与限制

- 安装测试依赖并实际启动 API/Web；和 A 对齐 RF-001 成功/错误公共样例后再定稿。Android 构建及分享验收依赖 A 的 RF-006。

## RF-002｜来源、候选事项与 Case 兼容契约

### 1. 任务信息

- 负责人：C；D 共审 Task/Evidence，A/B 审公共关系。日期：2026-11-05；基线/分支同上。
- 目标：说明现有关系、候选确认前后引用、旧数据兼容和依赖，给出可评审样例。
- 状态：C 侧提案与实验已有阶段成果，待 RF-001 共同口径及 D/A/B 确认；整卡未完成。无成果 commit/PR。

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

### 6. 运行证据

- 本分支中的契约与探针；本地日志 `.runtime/c-first-batch/probe.txt`（最终8项通过）、`probe-first-attempt.txt`（首次fixture错误）、`api-tests.txt`、`startup.txt`（入口缺依赖）、`docs.txt`（文档检查通过）。日志未提交、其他成员可用脚本复现。
- 参考的 D 交付：[PR #1](https://github.com/Hanxx1/RuleFlow/pull/1)，核对版本 d159808；不是 C 的实现/测试证据。
- C 成果 commit/PR、共同签认、截图和原始 Codex 会话分享/导出：待补充。

### 7. 未完成与限制

- RF-001 样例口径；D Q01/Q02 的 Evidence/独立Task、Q03 skipped、Q05 删除引用；B 文件与草稿/资料边界；A/B 对交互和迁移顺序的确认。
- 待团队评审才能定稿或进入依赖公共契约的正式功能；现在仍可完善独立走读/样例。RF-014/015/016/017、020/021、独立Task及共享附件功能均未在本轮实现。
- 公共文件修改须先沟通；当前改动留在本地任务分支，待用户核对再提交/推送。
