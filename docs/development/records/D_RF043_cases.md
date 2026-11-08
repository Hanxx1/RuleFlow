# 有绪 CampusWeave｜RF-043 准备子项测试矩阵

2026-11-05，D；源码 ac9e07c。状态：样例准备完成待评审；RF-043 算法修复未开始。当前最早可行方案不是多方案搜索/评分。下列“目标预期”未自动转为已通过。

## 合成基线及复现规则

默认时区 Asia/Shanghai，窗口 W=2099-01-01 08:00–12:00（+08:00），工作时段 08–21、缓冲 0、每日上限 780；A/B 各 30 分钟、todo、同 owner、有效 Evidence、通知 Review 已确认。API 样例按 `probe_boundaries.py` 的 setup_case 创建真实临时记录，不使用占位 ID 调接口。矩阵未覆盖的字段沿用默认；纯函数样例可用合成 case_id。

执行分类：E=现有测试本次执行通过；P=边界实验本次复现缺口；N=本次未运行的新样例。E 对应测试覆盖范围不等于下表所有数值变体都执行过。

| ID | 输入 / 操作 | 目标预期及依据 | 当前证据 / 待决 |
|---|---|---|---|
| S01 单任务 | 仅 A，无占用，W | A 为 08:00–08:30；预览不落正式安排 | E（2026-11-08）；test_s01_single_task_preview_does_not_save，精确时间及预览不写入通过 |
| S02 多任务依赖 | A→B，A 高低优先级互换 | 均必须 A 后 B；评分不得越过依赖/截止 | E `test_schedule_splits.py::test_priority_never_overrides_deadline_or_dependency` |
| S03 选集外耗时不足 | A 需90分钟，仅有08:00–08:30；只选 B，A→B | B 不应生成可提交建议；原因需说明前置耗时不足 | P external_predecessor：预览200，一条08:30建议；提交409，日程1→1；RF-043缺口 |
| S04 选集外足量/缺失 | A需90分钟，已安排08:00–09:30 / 完全无安排，只选B | 足量则B≥09:30；缺失则 blocked_by_predecessor | E（2026-11-08）；test_s04_external_predecessor 两变体通过：90分钟足量可预览并提交，缺失则阻断；S03不足量缺口仍未修 |
| S05 过去时间 | 只选B，窗口2000-01-01 08–12 | 拒绝或显式调整到now；禁止保存过去建议 | P past_window：预览200、提交200、日程0→1；Q08定拒绝/调整 |
| S06 草案自然过时 | 冻结now=2099-01-01 07:59生成08:00草案，now推进到08:31再提交 | 重新校验时间并拒绝，原日程不变 | N；目前无clock注入，未来用测试替身；不能用S05冒充本例 |
| S07 时区/纯日期截止 | timezone=UTC，截止2099-01-01，窗口17–20Z，任务30分钟 | 预览与提交采用同一截止时区 | P timezone_deadline：预览17Z建议，提交409超截止；日程0→0；Q08 |
| S08 课表变更 | 占用08–10、revision2，先不授权，再授权生成，提交revision3/2 | 未授权422；避开课；版本3拒绝、2允许 | E `test_client_calendar.py::test_calendar_consent_avoiding_courses_and_stale_draft` |
| S09 拆分/不可拆 | 90分钟，仅三个30分钟空隙；拆分允许/禁止 | 可拆完整3片；不可拆无建议，不留残片 | E `test_three_gaps_fit_split_task_and_unsplit_returns_conflict` |
| S10 尾段不足 | 90分钟，min=max=60，W无占用 | 不能把60分钟当完成；目标保留整任务撤回，是否允许尾段例外待Q06 | N；当前代码剩余<min无候选、撤回本任务全部片段 |
| S11 拆分次数上限 | 90分钟，3×30空隙，要求最多2片 | 无完整可行方案；不可忽略上限 | N；当前无最大次数字段，API形状待Q06 |
| S12 done/skipped | A→B，A状态分别done/skipped，只有B被选中 | done放行；skipped目标待Q03 | N；代码目前二者均放行，不据此签认需求 |
| S13 正式锁/已有占用 | 已保存08–09锁定项，编辑/删除；再生成建议 | 必须明确解锁；预览保留所有正式占用（非只锁定项） | E `test_schedule_series_locks.py::test_locked_item_requires_explicit_unlock_for_edit_delete`；预览保留占用系代码依据 |
| S14 未知耗时/变更 | A.duration=None；已有安排后PUT duration=90 | 未知估算应标待确认；已安排不能静默丢数据 | N；现状默认30，已有安排409；Q06 |
| S15 可用时间/日上限/缓冲 | 10–18、每日60、buffer15，A→B各60，窗口至少2天 | 不越上限/时段/依赖，缓冲占用生效 | E `test_schedule_preferences.py`三项（含已有task计入上限及秒级取整） |
| S16 空集/重复ID | task_ids缺省、[]、[A,A] | 新选择入口无选择不排全部；重复422 | N；现状前两者全选、重复422；Q07 |
| S17 owner/确认/幂等 | 其他owner提交草案；本owner consent=false；同草案重复commit | 404/422，无日程；重复不重复写入 | E `test_draft_owner_consent_atomic_commit_and_idempotence` |
| S18 状态过期 | 草案后新增占用或改变Case确认 | 409 DRAFT_STALE或相应门禁，无部分写入 | E `test_changed_occupancy_invalidates_whole_draft`、`test_changed_confirmation_invalidates_draft` |
| S19 分段提交/依赖保护 | A90分拆三片→B；先单独保存B；新增破坏既有后置的依赖 | 拒绝绕过，合法草案四片提交；非法新增依赖回滚 | E `test_split_commit_and_independent_successor_cannot_bypass_dependencies`、`test_new_dependency_cannot_break_an_existing_successor_schedule` |
| S20 时区输入/搜索范围 | 无offset时间、end≤start、窗口91天；无deadline窗口14天 | 无效输入422；无截止仍有界 | E（2026-11-08）；test_s20_invalid_window_rejected 五变体及 test_s20_no_deadline_defaults_to_fourteen_days 通过 |
| S21 多片中后片失败 | 草案两片，测试替身让第二次validate失败 | 事务回滚，第一片也不保存，草案仍pending | E（2026-11-08）；test_s21_second_validation_failure_rolls_back_and_allows_retry：事务内记录数0→1，注入409后0，草案pending且committed_at为空，恢复后重试保存2条 |

## 本次运行命令与结果

在仓库根目录，Windows / Python 3.11.6，使用已有 `.runtime/review-venv`；没有安装依赖。测试 conftest 使用内存数据库、临时上传目录，不访问真实账户或在线模型。

```powershell
& .runtime/review-venv/Scripts/python.exe -m pytest server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings
& .runtime/review-venv/Scripts/python.exe -X utf8 docs/development/records/evidence/D_20261105/probe_boundaries.py
& .runtime/review-venv/Scripts/python.exe scripts/smoke-startup.py
```

- 定向测试：14 passed、5 warnings，退出0，日志 `本地证据：.runtime/d-first-batch/evidence/pytest-scheduling.txt`。warnings未修复，不视作零告警。
- 探针：退出0，三个观察结果见 `本地证据：.runtime/d-first-batch/evidence/boundary-results.txt`。脚本是当前行为观察器，不断言缺陷已修好、不计“三个产品验收通过”。
- 后端真实HTTP健康/注册/验证/登录/事项往返：PASS，日志 `本地证据：.runtime/d-first-batch/evidence/startup.txt`；不等于浏览器或Android验收。
- 首次探针产生结果后清理临时SQLite报WinError32；改用与现有测试一致的内存库并显式关闭，重跑退出0。首次日志保留 `本地证据：.runtime/d-first-batch/evidence/boundary-first-attempt.txt`，含当时控制台编码乱码；首次临时目录可能残留，未自动删除未知路径。
- 首次按README使用 `server/.venv/Scripts/python.exe` 失败（文件不存在），未执行测试；随后改用已存在环境，没有把失败算作测试通过。

## 实施边界

本轮只新增样例文档和隔离观察脚本，未修改 solver、API、schema、数据库迁移或正式测试。待Q03/Q06/Q07/Q08确认后，把S03/S05/S07等目标转为定向回归，再实现RF-043；RF-044的候选枚举/评分另做，不把任务priority_score视作多方案评分。C需提供通知Task与依赖/截止的去标识样例，B需确认课表revision，A需复核解释与真机基线。所有N行尚未执行。

## 2026-11-08 补充验证：S01 / S04 / S20 / S21

基线 main `4f9b266`。新增 `server/tests/test_schedule_boundaries.py`，共10项参数化测试；使用已有隔离内存数据库、合成账户与临时目录，无真实账户或在线模型。仅增加测试和记录，未修改 solver、API、schema、迁移或 UI。

- S01：单任务精确08:00–08:30，预览不保存。
- S04：选集外90分钟前置完整安排后，后置09:30开始并可提交；无前置安排则 blocked_by_predecessor。
- S20：起点/终点无offset、相等、反向、91天窗口均422且不创建草案；无截止且省略终点时窗口为14天。
- S21：第二次真实校验后注入409，注入前确认事务内已写入第一条；失败整笔回滚，草案pending、committed_at为空；移除替身后同草案可重试成功。

命令：`.runtime/review-venv/Scripts/python.exe -m pytest server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings`

结果：24 passed、5 warnings，退出0（新10项＋既有14项）。本地日志 `.runtime/d-rf043-boundaries/pytest.txt`。本节更新上方对应行的执行状态，原有历史运行记录保留。S03/S05/S07未修复，本次未重跑其探针；其余N行仍未执行。未运行全量后端、Web/移动端或构建APK，无本次APK产物；未提交、推送或取得团队验收。