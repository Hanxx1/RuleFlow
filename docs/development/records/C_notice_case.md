# 有绪 CampusWeave｜成员 C 开发工作记录

## CM-002｜课程列表、详情与编辑交互样例（2026-11-10）

### 1. 任务信息

- 负责人 C。用户恢复 CM 开发后，继续此前暂停的 `feat/CM-002-course-pages`，fetch 后快进至 `origin/main` 的 `65977de`；未混入 RF-013 文档分支提交。
- 状态：**固定样例页面与基础编辑交互已实现并验证；CM-002 整卡未完成，未实现正式保存。** 本次尚未提交、推送或发起 PR。
- CM-001 的 C 侧提案位于独立提交 `dc046af`、PR #9；它仍是待共同评审方案，不视为已签认。没有将该分支的记录复制覆盖当前记录。

### 2. 技术实现

- 新增 [课程模块说明](../../../mobile/src/features/courses/README.md)、`CoursePreview.vue`、`demoModel.ts`、`demoModel.test.ts`、`preview.ts`，独立入口 [course-preview.html](../../../mobile/course-preview.html)。展示模型仅供模块样例使用，不是公共 schema。
- 用户转达 A／相关成员已确认导航接入范围后，修改 `mobile/src/router.ts` 增加懒加载 `/courses` 路由，修改 `HomeView.vue` 将“常见问题”快捷按钮替换为“我的课程”，新增课程图标 `mobile/public/assets/icons/features/icon_courses.svg`。帮助入口保留，底部四个导航不变；课程页可返回工作台。
- 列表支持学期筛选、独立课程身份；详情四区为总览、课程要求、任务、资料。支持新增样例、编辑名称/学期/教师/地点/小组成员与分工、取消编辑。
- 常用要求固定展示考勤、考试与评分、实验、分组、项目、作业；支持自定义字段。区分未记录、待核对、明确无要求、已确认；确认/待核对需要内容和依据，明确无要求需要依据且不得混留要求内容。人工修改追加旧值和旧依据，不覆盖旧要求历史。
- 所有数据为合成样例及本页人工输入，仅存组件内存，刷新重置。不访问账户、Workspace、后端或正式课表，不创建 Task/Case/Document，不改数据库、共享接口及 B/D 模块。

### 3. 设计与关键决策

- 按近期任务允许的 A 类切片先做页面/纯逻辑，正式保存等待 CM-001/RF-012。开发入口可直接运行，不需要提前修改主应用公共导航。
- 导航最初等待协调，随后用户明确答复“已确认，可以接入路由和工作台入口”，据此实施上述两个公共文件的最小改动；这项确认不扩展为 CM-001/RF-012 存储及公共协议签认。
- 任务/资料区明确“未查询”，不将消费者未接入显示成“没有任务/资料”。上课规则只说明等待对接，不重复实现 D 的排程占用。

### 4. 遇到的问题及解决

- 首次浏览器验证的功能断言均走通，但控制台出现缺省 favicon 的 404，最后健康断言失败；在独立入口补 data 图标后按原断言完整重跑通过，未忽略控制台错误。
- 主应用导航检查也发现 `http://127.0.0.1:5174/favicon.ico` 缺失，错误 location 已核实；当前主入口未配置图标且没有该静态文件。未改动主入口或扩大为全局资源修复；导航脚本严格的“无控制台错误”断言仍失败，不能声称主应用全部浏览器检查通过。
- 沙箱内本机 HTTP 访问报套接字权限错误，改用获工具批准的本机 Vite/Edge 运行验证；没有关闭业务安全检查。

### 5. 测试与验证

- `npm.cmd --prefix mobile test -- src/features/courses/demoModel.test.ts src/features/planning/ScheduleTimeGrid.test.ts src/views/GuideView.test.ts`：3 文件、18 项通过，其中新增模型测试 4 项覆盖跨学期身份、历史保留、未知/无要求门禁和重新打开样例。
- 导航接入后重新运行上述 18 项测试及 `npm.cmd --prefix mobile run build`，均通过；构建实际生成 `CoursePreview` 的 JS/CSS 懒加载块，主应用构建已包含课程样例页。独立课程预览 HTML 不作为单独生产入口，构建通过不表示已部署或正式存储已完成。Vite CJS 弃用警告仍存在。
- Browser 插件不可用，使用已安装 Playwright 1.62.1 + Edge 无头模式；URL 为 `http://127.0.0.1:5174/course-preview.html`，视口 390×844、1280×900。
- 实际走通学期筛选→同名春季课未记录→秋季课要求编辑→展开原始依据历史→阻止带内容的“明确无要求”→取消→新增自定义字段→任务/资料提示→取消档案编辑→新增下一学期同名课→回列表→刷新重置。两个尺寸无横向溢出；有页面标题/正文，无 Vite 错误覆盖层，无 pageerror/console error。
- 接入导航后重跑独立入口完整交互脚本，仍 PASS。另用 `check-cm002-navigation.cjs` 检查主应用 390×844／1280×900：工作台四个快捷按钮、帮助入口可达、课程图标加载、点击进入 `/courses`、详情要求区、返回工作台、直接访问/刷新 `/courses`、保留四个底部导航等断言通过；无横向溢出、无错误覆盖层和 pageerror。**脚本最终退出 1**，唯一 console error 为前述主应用 favicon.ico 404，保留失败断言，未报告全部通过。
- 未执行全量前后端回归、正式持久化重开或 Android 真机测试；浏览器仅验证合成样例。

### 6. 运行证据

- 仓库外本机会话证据目录：`C:/Users/Logic/.codex/visualizations/2026/11/10/01a1c334-39e1-7a90-bd33-02770c634d0a/`，实际生成 `check-cm002.cjs`、`cm002-mobile-list.png`、`cm002-mobile-requirements.png`、`cm002-desktop.png`；未随项目提交，其他设备不可直接访问，需共享时另行归档。
- 导航验证另生成同目录 `check-cm002-navigation.cjs`、`cm002-home-entry.png`、`cm002-integrated-requirements.png`；脚本失败输出包含 favicon 错误地址及断言，未抹去失败证据。
- 上述命令输出及 Playwright PASS 输出在本次 Codex 原始会话中。原始会话分享链接/导出归档：待补充，成员需保留。提交和 PR：待补充。

### 7. 未完成与限制

- 未接入日程网格点击、正式档案及要求存储/备份/恢复、真实 EvidenceRef、正式档案修订记录、快速/复杂规则编辑分层、小组作业真实关联及 B/D 消费者；样例来源不可用作真实业务证据。主应用 favicon 404 在下述 11-12 补测中已处理。
- 正式保存后的重开/账号切换/权限/revision/历史不覆盖仍待 CM-001/RF-012 实施后验证；内存样例刷新重置不能代替这项验收。
- 下一步审阅已接入的页面交互；取得对应契约确认后实现持久化切片。RF 的本地 `server/tests/test_import_recovery_guards.py` 原样保留，未修改，不属于本 CM 切片。

### 2026-11-12 页面切片收口与补测

1. **任务信息** — C；继续 `feat/CM-002-course-pages`，安全快进基线至 `a408d0a`。固定样例页面切片已完成本轮验证、待交叉评审；CM-002 整卡未完成。未提交、推送或创建 PR。用户明确转达 A／相关成员已确认允许在公共 `mobile/index.html` 补充 favicon 声明，该授权不扩展为正式存储或公共契约确认。
2. **技术实现** — `demoModel.ts` 增加仅用于样例的 `CourseProfile`、`profileHistory` 和 `updateCourseProfile`；保留旧名称、学期、教师、地点、小组，课程 ID 和要求/依据保持不变，相同内容保存不增加历史。`CoursePreview.vue` 在总览展示档案旧值，`demoModel.test.ts` 新增两项历史/校验回归。更新模块 README 和独立入口注释；`mobile/index.html` 复用独立样例入口的 `data:,` 空图标声明以阻止缺省 favicon 请求，无新增品牌图标或依赖。
3. **设计与关键决策** — 档案历史继续只存在组件内存，刷新重置，不声称正式审计或持久化完成。未修改 API、数据库、Workspace、Provider、B/D 模块或 Android。主线更新前以具名 stash 保存三份原有已跟踪改动；恢复时 C 记录发生内容冲突，合并保留 CM-002 与主线 RF-013 全部记录；stash 仍保留作备份。RF-013 未跟踪测试原样保留，不纳入课程切片。
4. **问题及解决** — Git fetch 因本机代理不可达失败，GitHub 只读提交查询确认最新主线仍为 `a408d0a`，使用已获取的 `origin/main` 快进。沙箱 Edge 启动时命名管道错误退出，正常本机权限下 Edge 无法访问沙箱 Vite；停掉本轮启动的沙箱服务，以工具批准的正常本机权限重新运行 Vite 和相同浏览器脚本后通过。未修改业务校验或降低断言。历史 favicon 控制台失败已由本轮相同导航脚本完整重跑关闭。
5. **测试与验证** — 在 Windows、既有 Node/依赖环境运行 `npm.cmd --prefix mobile test`：**22 文件、123 项通过，退出0**（课程模型6项）；`npm.cmd --prefix mobile run build`：类型检查及生产构建通过，204 modules，退出0，仍有既有 Vite CJS 弃用提示。Browser 插件未提供（Browser plugin not available），使用已有 Playwright 1.62.1／Edge，Vite 地址 `http://127.0.0.1:5174`。运行仓库外 `check-cm002.cjs` 和 `check-cm002-navigation.cjs` 均 PASS／退出0，覆盖学期隔离、四区、要求编辑/原依据保留、无要求门禁、自定义字段、取消/新增、档案两次修改与不变保存、要求未被覆盖、刷新重置、首页四入口/帮助/课程图标、往返/直达/刷新和底部导航。390×844、1280×900 无横向溢出、Vite 错误覆盖层、pageerror 或 console error；已人工查看手机首页及档案历史截图。未运行后端全量、真实账户存储/网络/模型、Android 或真机测试，无新 APK。
6. **运行证据** — 本轮脚本及截图实际位于仓库外 `C:/Users/Logic/.codex/visualizations/2026/11/12/01a1ce77-130c-7842-a56d-f18286d84a19/`，包括 `check-cm002.cjs`、`check-cm002-navigation.cjs`、`cm002-profile-history.png`、`cm002-home-entry.png`、`cm002-integrated-requirements.png`、`cm002-mobile-list.png`、`cm002-mobile-requirements.png`、`cm002-desktop.png`。仅本机可访问，未随项目提交；构建、123项测试和浏览器PASS输出见本次原始会话。原始 Codex 会话分享／导出待 C 保存，开发记录不能替代它。
7. **未完成与限制** — 正式保存与重开、owner/revision、真实 EvidenceRef、备份恢复及 B/D 真数据联动仍待 CM-001/RF-012 对应决策与实现；未改写他人的唯一公共决策表、未将 PR #9 或 #12 当作课程契约已批准。后续先交叉评审当前页面切片，同时按 D-CM-01～06 收口 C 的课程身份/确认流程意见，再进入获确认的持久化切片。

补充静态验证：使用既有 `.runtime/c-venv/Scripts/python.exe -X utf8` 运行 `scripts/check-docs.py`（207个本地链接/图片目标）、`scripts/check-paths.py`，以及 `node scripts/check-demo.mjs`（8份副本一致）和 `git diff --check`，均通过。最终无未解决的 Git 冲突、无暂存内容；独立 RF-013 测试文件 SHA-256 前后均为 `66043c97597546d861d579733fe63321de6b9c2089014100510b637b20926ed5`，确认未修改。

提交授权补记（2026-11-12）：用户已审阅页面切片说明并明确要求“提交推送”。上述“未提交/推送”为验证阶段状态；本次仅交付 CM-002 的页面、模型、测试、入口及本记录，排除独立 RF-013 失败回归文件，不创建 PR 或合并。实际 commit 与远端分支状态以 Git 历史和推送结果为准。

## 当前进度与下一工作入口（2026-11-10 历史快照）

本节只索引下方原任务记录，不新建平行验收结论。当时安排为：**暂停 CM 开发，先完成 C 的近期 RF 工作**；后续已恢复 CM 页面开发，最新进展见上方 CM-002 的 11-12 补记。团队任务编号、分工、检查点及验收标准保持原约定。

### 已核对的版本与交付

| 范围 | 真实成果与版本 | 当前状态/限制 |
|---|---|---|
| RF-001 C 走读 | 早期服务/API走读和启动证据见原条目；2026-11-10另完成现有前后端本机试用与390×844浏览器入口检查，源码d1d8647 | 已有C侧有限走读/运行证据；未替全员或Android基线验收 |
| RF-002 C 契约/评审 | `786815c`/`8094f38` 首轮及补测、`f34e70e` 交叉评审已在main；PR #2/#6 已合并，可由Git历史核对 | C提案/消费意见已有；Q01/Q02团队签认仍以D唯一决策表为准，未实现多候选存储/确认 |
| RF-011/013 来源移交 | `6a6b20b`及PR #7已在main；现有API三项测试与只读form-context提案 | 新接口仍未获B/A/B确认、未实现；H04/H05/H06/H08未验 |
| RF-013 H07诊断 | `b179902`、[PR #10](https://github.com/Hanxx1/RuleFlow/pull/10)、`docs/RF-013-recovery-validation`已推送 | 按open过滤查询确认PR开放；5项边界符合、3项OPEN_GAP，两类缺口未修复；没有本轮评审获批依据 |
| CM-001 C侧准备 | `dc046af`、[PR #9](https://github.com/Hanxx1/RuleFlow/pull/9)、`docs/CM-001-course-contract`已推送 | PR开放且未进入本次main；提案/样例不是团队定稿。仅保留历史成果索引，CM继续暂停 |
| CM-002 | 曾创建 `feat/CM-002-course-pages`，未提交课程页面或业务代码 | 暂停，不因分支存在记为功能已实现；不纳入当前编码范围 |

本轮 `git fetch origin --prune` 后，远端main为 **`65977de`**，当前工作分支仍为 **`docs/RF-013-recovery-validation` / `b179902`**；工作区开工时干净。`git branch -r --contains`显示RF-013诊断和CM-001分别仅在对应远端任务分支，尚未进入main。复用当前RF-013分支补充文档，未合并main、cherry-pick、重写历史或修改其他成员记录。

最新main新增 `9b1d2ae`：导入进度查询在 created_at 相同时增加 rowid 降序，定位最新重试；随提交新增对应回归用例。已读实际diff，**未在该新版本执行测试**；不能将本分支的12项通过套用到最新main。它只改重试查询，不修复附件HTML误成功或解析失败来源关联缺失。下一代码切片必须重新fetch并核对这个公共main.py基线，避免覆盖它。`65977de`同时包含D的网格移动显示修复，该成果不归C认领，也不据此恢复CM开发。

### 下一阶段顺序（建议，尚未启动实施）

| 顺序/任务 | 下一份可评审交付 | 必要前置与验收 |
|---|---|---|
| 1：RF-013 H07收口 | 请B/A/B核对已复现的两类缺口、附件失败展示/错误语义和正式来源关系；PR #10作为共同证据 | 现有探针和修复矩阵可直接评审；在本记录补确认人/日期/范围，不把文档或PR开放当已批准 |
| 2：RF-013最小修复 | 确认后另开 `fix/RF-013-attachment-recovery`，优先两个可分审的小切片：附件HTML不可当有效文件；解析失败Document与来源保持正式关系 | 新分支从届时最新main开始，声明main.py及相应测试占用；保留普通HTML通知导入、owner/consent、父来源、错误隐私及事务保护。三项OPEN_GAP须有失败→通过断言；不迁移/批修旧库，不新建候选系统 |
| 3：RF-011/013正式读取最小链 | B及A/B确认form-context后，实现只读正文/原行/原件引用读取和H04/H05；B接1C后共同验H06 | 先确认URL/DTO、legacy_text、expected_revision及失败源读取；保持同owner/当前batch/正式关系/原件hash校验，无模型调用或正式Case/Task创建 |
| 并行准备：RF-002/003、RF-008～010 | C补受影响来源/证据样例，推进Q01/Q02及RF-012消费确认；可整理Fake Provider的最小能力输出/引用/失败样例 | 只做当前消费者所需准备，不修改未确认公共Provider/Schema。Q03～Q10按实际依赖，不等待全表才能做无关验证 |
| 后续：RF-014～018、RF-020/021、RF-040 | 多候选与确认、材料匹配、独立清单分别按原任务卡拆小切片 | 候选正式存储等RF-002/008及迁移顺序；材料等RF-011/012；独立清单真实接入等D的RF-038/039，不做假Case或第二套Task |

优先保持一个主要实现切片。团队计划11-13契约/基线检查、11-20基础模块门槛保留；本节不更改日期、不承诺未获确认部分届时完成。若前置未过，按具体消费者列受阻，其他已授权验证/样例继续。

本次只同步进度与技术说明，**未重新执行产品功能测试**，不更新历史测试数字为“最新全量通过”；文档检查结果见RF-013续记。尚未提交本次文档更新，未推送或修改PR；重要原始会话分享/导出仍需C保留。

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
- 初始记录时H04–H08未执行；2026-11-10仅H07已补合成探针，结果见下方续记，仍有未修复缺口。H04/H05新接口、H06消费和H08真机仍未执行，真实同通知多份原表待样本。未宣称HTML登录页识别、自动重试、移交UI或正式草稿已完成。
- RF-002/003 最终签认与 RF-015/038/039 迁移顺序仍待团队决定；D 排程缺口不在本轮修复。

#### 2026-11-10 续记：H07 现有失败链验证与修复准备

**1. 任务信息**

- RF-013 原任务续记，负责人 C；用户明确暂停 CM 开发，优先 RF 近期工作。用户反馈 B 与 A/B 尚未确认 form-context，选择“先做现有链路验证与修复准备”；不将该指令理解为新共享接口或公共文件修复已获团队确认。
- 诊断执行时fetch后的origin/main为 `d1d8647`；独立分支 `docs/RF-013-recovery-validation`，未带入CM-001分支改动。状态：H07合成失败链诊断与修复方案准备完成，已发现开放缺口；RF-013整卡未完成。其后已获授权提交推送，实际提交 **`b179902`**；本次进度核对发现 [PR #10](https://github.com/Hanxx1/RuleFlow/pull/10) 已存在且开放，尚未进入main。不是本次文档更新创建的PR，也不表示修复或接口方案已获批。

**2. 技术实现**

- 新增 [probe_rf013_recovery.py](evidence/C_20261110/probe_rf013_recovery.py)，从自身路径定位仓库，复用真实 FastAPI 路由、内存 SQLite、临时原件、合成账户及 TestClient。仅外部获取与一次解析错误使用受控替身；无真实网络/OCR/模型。
- 探针记录8项边界观察：附件发现、拒绝前不抓取、403保留父来源、手工替换、登录HTML、错误HTML、解析失败原件保护及正式关联。遇到开放目标缺口返回退出2；退出1表示探针异常，不把发现缺陷包装成测试全通过。
- 未改生产业务、API/Schema、数据库、原前端、Provider、Android 或其他成员记录；没有实现 form-context，没有继续 CM 功能。当前本机试用服务的数据未用于实验。

**3. 设计与关键决策**

| 定位 | 实测事实 | 待评审的最小修复建议/影响 |
|---|---|---|
| `main.py::import_attachment_candidate` 调用普通 `add_import_url_source` | 候选路径为 form.pdf，但返回 text/html 时按普通网页解析并存为 ready；登录页/错误页两例均增加可分析来源 | 在已确认获取的附件路径上检查返回类型，遇 HTML 不作为成功文件；保留原 URL、父来源、安全错误码，提示手动下载上传。普通通知网页导入仍允许 HTML，不全局禁用网页解析；不按“登录”关键词猜授权，也不绕过登录。具体错误码和“HTML包装下载页”展示语义待 B/A/B 确认 |
| `main.py::add_import_file_sources` 的异常顺序 | Document 已保存、parser失败后，在插入 source_documents 之前抛错；失败源 metadata 有 document_id，但正式关联为0条 | 对已经校验并落盘的 Document，在失败来源保存后也建立同 owner、当前 source 的正式关联；格式/签名校验失败且无 Document 时不伪造关联。需审查事务失败和引用删除影响；不修改 Document 原件保护、解析状态或既有成功路径 |
| form-context 的后续消费 | 不能只信任 metadata 的 document_id，也不能假定所有失败源无原件 | 新接口仍待确认。读取时区分“解析失败但原件在”“未取得文件”“原件缺失”；不能通过放松 owner/批次/正式关系校验掩盖上述缺口。历史孤立关系的检测/补齐另提方案，不先批量修库 |

两类修复均需触及公共高冲突文件 `server/app/main.py`，应先给 B/A/B 核对附件结果消费与来源/原件关系，再在明确范围内修复；不擅自认定团队已确认。无须为本轮诊断新增依赖或迁移；正式修复是否需要其他结构调整仍按评审结论，不预占迁移编号。

拟修复验收：登录/错误HTML不得成为成功附件，普通HTML通知仍能导入，合法TXT/已适配文件附件不回归；未授权/越权/跨批次/非法候选在抓取前拒绝；403和解析失败有准确状态，成功父来源不丢失；解析失败原件仍可由owner下载、正式关系存在，其他owner拒绝；校验失败没有伪造Document；中途关联写入失败不留下假成功。将这些目标落实为生产修复的回归断言后，探针对应OPEN_GAP才可关闭。

**4. 遇到的问题及解决**

- 复现两类产品缺口、共3个OPEN_GAP观察：登录HTML/错误HTML被标ready，以及解析失败原件没有正式来源关联。当前未修复，不调整断言或放松校验来获得绿灯。
- 探针使用外部响应替身，403由受控HTTPException模拟；它验证导入层的错误处理，不证明真实网站跳转/权限/网络获取已验收。解析失败由有效TXT通过文件校验后注入，未运行OCR或真实Office解析失败样本。

**5. 测试与验证**

环境为既有 `.runtime/c-venv`、Windows；正常本机权限运行以避免历史沙箱临时目录创建/清理限制。所有数据库/原件均在探针或pytest的独立临时空间。

```powershell
.runtime/c-venv/Scripts/python.exe -X utf8 docs/development/records/evidence/C_20261110/probe_rf013_recovery.py
.runtime/c-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_notice_handoff_baseline.py server/tests/test_document_api.py server/tests/test_link_candidates.py server/tests/test_analysis_retry.py -q -p no:cacheprovider --tb=short
```

- 探针退出 **2**：5项目标边界符合、3项开放缺口；这是缺陷复现，不是验收通过。未授权422、另一owner404、跨批次404、非法候选422，额外抓取0次，原批次revision和来源数不变。403子来源failed/url_http_error，父原件可读，手工移除失败源再上传成功后保留父来源、case_id仍为空。
- 登录HTML和错误HTML：均 source_status=ready、stored_mime=text/html、Document存在、analyzable_count=2，不满足“不是已取得的有效附件”的目标。不能据此推断所有HTML都是登录页；合成输入类型事先已知。
- 解析失败：source failed、DOCUMENT_PARSE_FAILED，原件字节一致，跨owner404，原始异常未泄露；metadata含Document ID，但对应source_documents_count=0。
- 定向pytest：**12 passed，5 warnings，2.37s，退出0**，覆盖既有来源/Document/附件/重试保护；5条为已有FastAPI/Starlette/AnyIO弃用警告。它们未覆盖新发现的3个缺口，不能替代修复验收。
- `python scripts/check-docs.py`：203个本地目标存在；`python scripts/check-paths.py`：活跃源码路径检查通过；`node scripts/check-demo.mjs`：8份样例副本一致；`git diff --check`通过，均退出0。新增探针已实跑并人工阅读，不以仅检查已跟踪diff替代新增文件审查。未运行全量后端、前端/浏览器、新共享接口、并发、旧库迁移、真实网络/模型或Android验证。

**6. 运行证据**

- 可复现脚本随本分支保留；本地 `.runtime/c-rf013-recovery/probe.json` 为实际8项观察，`.runtime/c-rf013-recovery/regression.txt` 为定向pytest输出，均位于忽略目录，不保证其他机器存在。
- 真实执行命令和输出在原诊断Codex会话；未生成截图/APK/产品回执。诊断提交 `b179902`、PR #10已核对；团队确认链接仍待补充，请C保留原始会话分享或导出。

**7. 未完成与限制**

- 两类缺口尚未修复；下一步先确认上述公共文件修复范围和错误语义，再进入最小修复及失败→通过回归。尚未获得B/A/B对来源移交提案的确认，H04/H05新接口、H06填表消费、H08真机仍未执行。
- H07只完成合成边界验证与修复准备；真实附件网站、格式覆盖、页面恢复交互、生产数据兼容和正式移交仍需后续验证。不将本次12项回归或5项探针符合写成RF-013整卡完成。

本次进度同步仅修改C的工作记录与RF-013技术说明（按用户“更新我的相关开发文档”要求），未重跑产品测试，未实施修复。实际检查：`python scripts/check-docs.py`通过（204个本地链接/图片目标）；`python scripts/check-paths.py`通过；`node scripts/check-demo.mjs`通过（8份副本一致）；`git diff --check`通过，均退出0。这些是文档/静态检查，不是最新main功能回归。本次两份文档改动尚未提交、推送，未更新PR或合并分支。

#### 2026-11-10 开发启动：RF-013失败回归（RED阶段）

**1. 任务信息** — C；用户要求开始下一阶段开发，首切片选择已复现的RF-013两类缺口。公共 `main.py` 修复范围的团队确认问题已提出，尚未收到答复；先新增失败回归，不把开工指令当作团队已签认。当前仍在 `docs/RF-013-recovery-validation` / `b179902`，原两份未提交文档更新保留；尚未创建修复分支或提交。

**2. 技术实现** — 本地新增 `server/tests/test_import_recovery_guards.py`（未跟踪，**不随本次文档更新交付**）：7个参数化后用例，覆盖附件HTML/XHTML不可成功、普通HTML通知与合法TXT附件、授权/owner/跨批次/索引拒绝、parser失败原件及正式关系、无效PDF不伪造Document。使用既有隔离fixture及合成数据，无新依赖、生产代码、共享接口或数据库修改。

**3. 设计与关键决策** — 从诊断观察转为可作为修复门禁的目标断言，HTML两种场景外另补XHTML；不预定新错误码，仅要求真实失败状态及安全错误码。保留普通通知HTML能力和既有来源保护。正式修复仍需范围确认，后续在最新main基线建立独立修复分支，不把当前RED测试直接提交到文档PR。

**4. 问题及处理** — 托管worktree创建调用长时间未返回，已终止等待；之后 `git worktree list` 确认仅原工作区，没有已创建的新工作区。未使用CLI绕过创建托管worktree；先在当前工作区仅新增回归文件，既有两份文档未被覆盖。测试失败为目标产品缺口，未删除断言、跳过用例或修改fixture掩盖。

**5. 测试与验证** — 实际运行：

```powershell
.runtime/c-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_import_recovery_guards.py -q -p no:cacheprovider --tb=short
```

正常本机权限运行，**4 failed、3 passed、5 warnings，2.63s，退出1**。三种HTML/XHTML的failed目标断言因实际ready失败，parser失败文件的正式关联断言因实际0条失败；其他三个保护用例通过。5条警告为既有FastAPI/Starlette/AnyIO弃用。结果适用于当前b179902（业务基线d1d8647），未在最新main65977de重跑、未进入GREEN阶段，不是功能验收完成。

**6. 运行证据** — 本地未提交的回归源文件与真实命令输出；忽略目录 `.runtime/c-rf013-recovery/red-regressions.txt` 保留本机日志。该RED文件和日志不在本次文档提交范围，其他成员不能从本次文档更新取得该文件；已提交的诊断脚本 `b179902` 仍可用于复现原两类缺口。无APK、截图或产品回执。原始会话分享/导出待C保存。

**7. 未完成与限制** — 等待B/A/B对两类公共修复范围的确认后再修改main.py；form-context不在本轮范围。下一步保护当前文档改动与RED证据，从最新main建立修复分支，完成最小修复、失败→通过及相关旧链路回归，再更新RF-013原记录。新RED文件尚未提交，不建议单独推入当前文档PR；CM继续暂停。

提交准备范围仅为 `C_notice_case.md` 与 `C_RF013_source_handoff.md` 两份文档，仍如实保留RED结果及待确认状态；测试源文件留在本地，待正式修复与GREEN回归后随修复分支交付。本次准备不表示已提交、推送或获得公共修复确认。

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

#### 2026-11-10 现有项目试用补记

对上述历史“Web未验证”作范围补充：已在 `d1d8647` 源码启动Vite及FastAPI供本机试用，后端使用 `.runtime/local-preview` 的独立试用库/文件目录，未配置真实LLM。使用本机已有Playwright＋Edge headless在390×844加载首页，点击“执行计划→查看时间网格样例”，并分别加载填表演示与本机课表；无pageerror、无Vite错误遮罩，最后课表页面无横向溢出，后端health为200/local-text-only。首页/网格截图曾在原会话展示。命令及截图证据在原会话，仓库内尚无这次UI验证的可复现脚本/截图索引；未把外部截图或试用库提交。

没有运行完整前端测试/构建、账户完整链路、多浏览器/多尺寸或Android，不能将四个入口检查当成RF-001全员验收。试用时发现沙箱Vite占端口却不响应，清理本次启动的无响应进程后改用本机后台进程成功；没有改生产代码。该条只记录当时启动与验证事实，不保证未来进程持续存活或产物可用于设备验收。

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
