# 有绪 CampusWeave｜D 首批评审说明

状态：待团队评审；交付分支 `docs/RF-003-RF-043-prep`，实际提交以该分支 Git 历史为准。未创建 PR，未发送团队消息。

## 问题与实际交付

Task、Schedule、Evidence 的关系与排程边界需要团队先达成一致，才能安全开发独立清单和排程增强。本轮交付 Task→草案→提交走读、RF-003 契约提案、21 组 RF-043 样例，以及可复现的 API 边界观察和 Web 页面实验脚本。

- [D 工作记录](D_scheduling.md)：各任务七项记录与实际验证范围。
- [契约草案](D_RF003_contract.md)：当前行为、推荐行为及兼容影响。
- [测试矩阵](D_RF043_cases.md)：已运行、缺口复现、未运行分开标识。
- [公共决策表](D_public_interface_questions.md)：Q01–Q10 全部待共同确认。
- 实验脚本：`evidence/D_20261105/probe_boundaries.py`、`web_check.py`。

业务源码、schema、数据库迁移、API、UI、依赖锁文件及 Android 配置均未修改。新增名称使用有绪 CampusWeave，旧名称未全局替换。

## 分支与证据提交范围

- 基线 ac9e07c；分支 `docs/RF-003-RF-043-prep`，由应用原生工具创建独立工作区。
- 原 main 目录的本任务材料已逐文件备份并校验后迁移，main 未提交修改且工作区干净。
- 本次提交范围仅包括本目录五份 Markdown 和两份实验脚本。原始日志、截图、临时数据库、浏览器资料与依赖位于忽略目录，不提交。
- 原始证据本地位置：`.runtime/d-first-batch/`。评审者可运行脚本复现；本地位置不是可供他人直接访问的共享链接。
- 原始会话导出/分享链接待成员 D 保存。正文摘要不能替代原始会话证据。

## 验证及复现

Windows；后端 Python 3.11.6，复用原目录已有 review-venv；Web 实验宿主 Python 3.14、已有 websocket-client、Node/Vite、Chrome headless。独立工作区 node_modules 为指向原目录已有依赖的本机 junction，仅用于本次验证；未安装依赖，不把缓存/链接当交付内容。独立数据和端口与其他成员隔离。

以下命令在仓库根执行，`CAMPUSWEAVE_TEST_PYTHON` 须指向安装仓库后端依赖的 Python。原工作记录中的 review-venv 相对命令属于迁移前实际执行历史，不表示新工作区自带该环境。

```powershell
& $env:CAMPUSWEAVE_TEST_PYTHON -m pytest server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings
& $env:CAMPUSWEAVE_TEST_PYTHON -X utf8 docs/development/records/evidence/D_20261105/probe_boundaries.py
python -X utf8 docs/development/records/evidence/D_20261105/web_check.py
```

- 新工作区定向基线：14 passed、5 warnings，退出0。
- Web实测：390×844，合成数据由API准备，页面完成登录、查看任务、预览、取消确认及确认保存；正式日程数0→0→0→2。保存成功页面截图已查看。
- Web脚本移入交付目录并使用环境变量后再次运行通过。第一版脚本因确认弹窗阻塞超时，修正的是实验脚本，非应用源码。
- 取消只验证确认弹窗的取消；当前没有独立取消草案按钮。未验证Android、触屏手势、完整视觉/无障碍矩阵、在线LLM或全量回归；无APK产物。
- 三项API缺口保持未修：选集外前置耗时不足、过去窗口可保存、UTC纯日期截止口径不一致。既有14项测试通过不能说明这些缺口已修复。

## 请求团队评审的内容

1. C 与 D 先对齐 Q01/Q02 的 Task/Evidence 归属，复用 C 的 RF-002，避免平行证据体系。
2. C/D、A/B 确认 Q03/Q06/Q07/Q08 中 skipped、耗时拆分、空选集、时区/过去时间语义；再固定 RF-043 争议预期。
3. B 确认 RF-012 的课程 revision/用途授权边界，A 核对首批验收与后续公共文件占用。
4. Q04/Q05/Q09/Q10 按其实际依赖推进；不要求先完成全部未来设计才能继续独立样例研究。

## 下一项与回退点

现在可继续补尚未运行的纯算法/事务边界样例、准备RF-007权限/取消用例。RF-003定稿前不实施038/039迁移，不提前修改solver。下一轮修复需声明公共文件范围并按相关单测验收。

本次未改变运行代码，无运行行为回退需求；若放弃提案只需撤回本分支的文档与实验材料，保留本地原始证据，不应重置或删除其他成员工作。
