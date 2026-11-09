# 有绪 CampusWeave｜RF-043 准备子项测试矩阵

2026-11-09当前状态：基线 d8672de，分支 fix/RF-043-scheduling-consistency。S03、S05/S06、S07 后端局部修复已完成，后端全量223项回归通过；页面恢复已修复并通过真实API移动回归，RF-043整卡及真机仍未验收。修复均未提交/推送。最早可行方案不是多方案搜索/评分；未执行目标不自动转为通过。

最新汇总、命令及页面证据见 [RF-043收口检查](D_RF043_closeout.md)。下方带日期的早期记录保留为历史，不代表当前状态。

## 合成基线及复现规则

默认时区 Asia/Shanghai，窗口 W=2099-01-01 08:00–12:00（+08:00），工作时段 08–21、缓冲 0、每日上限 780；A/B 各 30 分钟、todo、同 owner、有效 Evidence、通知 Review 已确认。API 样例按 `probe_boundaries.py` 的 setup_case 创建真实临时记录，不使用占位 ID 调接口。矩阵未覆盖的字段沿用默认；纯函数样例可用合成 case_id。

执行分类：E=现有测试本次执行通过；P=边界实验本次复现缺口；N=本次未运行的新样例。E 对应测试覆盖范围不等于下表所有数值变体都执行过。

| ID | 输入 / 操作 | 目标预期及依据 | 当前证据 / 待决 |
|---|---|---|---|
| S01 单任务 | 仅 A，无占用，W | A 为 08:00–08:30；预览不落正式安排 | E（2026-11-08）；test_s01_single_task_preview_does_not_save，精确时间及预览不写入通过 |
| S02 多任务依赖 | A→B，A 高低优先级互换 | 均必须 A 后 B；评分不得越过依赖/截止 | E `test_schedule_splits.py::test_priority_never_overrides_deadline_or_dependency` |
| S03 选集外耗时不足 | A 需90分钟，仅有08:00–08:30；只选 B，A→B | B 不应生成可提交建议；原因需说明前置耗时不足 | E（2026-11-09局部修复）；preview/drafts对30/90及89/90分钟均阻断，旧草案提交409且无写入；18项S03测试及相关回归共42通过，详见文末 |
| S04 选集外足量/缺失 | A需90分钟，已安排08:00–09:30 / 完全无安排，只选B | 足量则B≥09:30；缺失则 blocked_by_predecessor | E（2026-11-08）；test_s04_external_predecessor 两变体通过：90分钟足量可预览并提交，缺失则阻断；S03不足量已于2026-11-09修复，见S03与收口记录 |
| S05 过去时间 | 只选B，窗口2000-01-01 08–12 | 按用户确认直接拒绝过去起点；禁止保存过去建议 | E（2026-11-09）；用户确认直接拒绝，两入口对过去起点422，无草案/日程写入；时区等价/微秒边界通过 |
| S06 草案自然过时 | 冻结now=2099-01-01 07:59生成08:00草案，now推进到08:31再提交 | 重新校验时间并拒绝，原日程不变 | E（2026-11-09）；时间流逝后409 DRAFT_EXPIRED整份拒绝，日程不变、草案pending；晚到幂等重试通过 |
| S07 时区/纯日期截止 | timezone=UTC，截止2099-01-01，窗口17–20Z，任务30分钟 | 预览与提交采用同一截止时区 | E（2026-11-09）；用户确认上海纯日期口径，预览排序/紧迫度/窗口与提交统一；S07共21项无xfail，扩展相关回归99通过 |
| S08 课表变更 | 占用08–10、revision2，先不授权，再授权生成，提交revision3/2 | 未授权422；避开课；版本3拒绝、2允许 | E `test_client_calendar.py::test_calendar_consent_avoiding_courses_and_stale_draft` |
| S09 拆分/不可拆 | 90分钟，仅三个30分钟空隙；拆分允许/禁止 | 可拆完整3片；不可拆无建议，不留残片 | E `test_three_gaps_fit_split_task_and_unsplit_returns_conflict` |
| S10 尾段不足 | 90分钟，min=max=60，W无占用 | 不能把60分钟当完成；目标保留整任务撤回，是否允许尾段例外待Q06 | N；当前代码剩余<min无候选、撤回本任务全部片段 |
| S11 拆分次数上限 | 90分钟，3×30空隙，要求最多2片 | 无完整可行方案；不可忽略上限 | N；当前无最大次数字段，API形状待Q06 |
| S12 done/skipped | A→B，A状态分别done/skipped，只有B被选中 | done放行；skipped目标待Q03 | E（兼容行为）；S03回归覆盖done/skipped放行；skipped产品语义仍待Q03，不据此签认需求 |
| S13 正式锁/已有占用 | 已保存08–09锁定项，编辑/删除；再生成建议 | 必须明确解锁；预览保留所有正式占用（非只锁定项） | E `test_schedule_series_locks.py::test_locked_item_requires_explicit_unlock_for_edit_delete`；预览保留占用系代码依据 |
| S14 未知耗时/变更 | A.duration=None；已有安排后PUT duration=90 | 未知估算应标待确认；已安排不能静默丢数据 | N；现状默认30，已有安排409；Q06 |
| S15 可用时间/日上限/缓冲 | 10–18、每日60、buffer15，A→B各60，窗口至少2天 | 不越上限/时段/依赖，缓冲占用生效 | E `test_schedule_preferences.py`三项（含已有task计入上限及秒级取整） |
| S16 空集/重复ID | task_ids缺省、[]、[A,A] | 新选择入口无选择不排全部；重复422 | N；现状前两者全选、重复422；Q07 |
| S17 owner/确认/幂等 | 其他owner提交草案；本owner consent=false；同草案重复commit | 404/422，无日程；重复不重复写入 | E `test_draft_owner_consent_atomic_commit_and_idempotence` |
| S18 状态过期 | 草案后新增占用或改变Case确认 | 409 DRAFT_STALE或相应门禁，无部分写入 | E `test_changed_occupancy_invalidates_whole_draft`、`test_changed_confirmation_invalidates_draft` |
| S19 分段提交/依赖保护 | A90分拆三片→B；先单独保存B；新增破坏既有后置的依赖 | 拒绝绕过，合法草案四片提交；非法新增依赖回滚 | E `test_split_commit_and_independent_successor_cannot_bypass_dependencies`、`test_new_dependency_cannot_break_an_existing_successor_schedule` |
| S20 时区输入/搜索范围 | 无offset时间、end≤start、窗口91天；无deadline窗口14天 | 无效输入422；无截止仍有界 | E（2026-11-08）；test_s20_invalid_window_rejected 五变体及 test_s20_no_deadline_defaults_to_fourteen_days 通过 |
| S21 多片中后片失败 | 草案两片，测试替身让第二次validate失败 | 事务回滚，第一片也不保存，草案仍pending | E（2026-11-08）；test_s21_second_validation_failure_rolls_back_and_allows_retry：事务内记录数0→1，注入409后0，草案pending且committed_at为空，恢复后重试保存2条 |

## 2026-11-05 历史运行命令与结果

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

## 2026-11-05 历史实施边界

本轮只新增样例文档和隔离观察脚本，未修改 solver、API、schema、数据库迁移或正式测试。待Q03/Q06/Q07/Q08确认后，把S03/S05/S07等目标转为定向回归，再实现RF-043；RF-044的候选枚举/评分另做，不把任务priority_score视作多方案评分。C需提供通知Task与依赖/截止的去标识样例，B需确认课表revision，A需复核解释与真机基线。所有N行尚未执行。

## 2026-11-08 补充验证：S01 / S04 / S20 / S21

基线 main `4f9b266`。新增 `server/tests/test_schedule_boundaries.py`，共10项参数化测试；使用已有隔离内存数据库、合成账户与临时目录，无真实账户或在线模型。仅增加测试和记录，未修改 solver、API、schema、迁移或 UI。

- S01：单任务精确08:00–08:30，预览不保存。
- S04：选集外90分钟前置完整安排后，后置09:30开始并可提交；无前置安排则 blocked_by_predecessor。
- S20：起点/终点无offset、相等、反向、91天窗口均422且不创建草案；无截止且省略终点时窗口为14天。
- S21：第二次真实校验后注入409，注入前确认事务内已写入第一条；失败整笔回滚，草案pending、committed_at为空；移除替身后同草案可重试成功。

命令：`.runtime/review-venv/Scripts/python.exe -m pytest server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings`

结果：24 passed、5 warnings，退出0（新10项＋既有14项）。本地日志 `.runtime/d-rf043-boundaries/pytest.txt`。本节更新上方对应行的执行状态，原有历史运行记录保留。S03/S05/S07未修复，本次未重跑其探针；其余N行仍未执行。未运行全量后端、Web/移动端或构建APK，无本次APK产物；未提交、推送或取得团队验收。
## 2026-11-09 S03 回归与差异定位

基线main `4144bdb`；按用户要求仅补测试、定位和最小修复方案。新增 `server/tests/test_schedule_predecessor_duration.py`：preview/drafts两个入口×30/90及89/90分钟四项预览目标；两项旧不合法草案提交保护。初次运行4 failed、2 passed；最终用专用异常限定strict xfail，相关排程合跑26 passed、4 xfailed、5 warnings，退出0。xfail为仍存在的缺陷，不是修复通过；`--runxfail`可重新暴露。

预览未传外部前置耗时且只判断已有结束时间，提交则查询耗时并累计实际安排。拟通过内部耗时映射和足量判断修复，详见[最小修复方案](../../superpowers/plans/2026-11-09-rf043-s03-predecessor-duration.md)。本轮未改生产逻辑/API/迁移/UI，无APK、无全量回归，未提交或推送；S03仍开放。


## 2026-11-09 S03 局部修复验证（最新）

用户随后授权实施最小方案，不提交/推送。预览现在传入同owner的耗时元数据，对外部前置累计分钟不足或元数据缺失时阻断；足量后仍以最后一片结束时间为下界。提交防线不变。

`test_schedule_predecessor_duration.py`现有18项，已移除全部xfail；加既有24项共42 passed、5 warnings、退出0。包含多片段60/90与90/90、done/skipped兼容、缺元数据、None默认30分钟边界、无关任务、31分钟HTTP预览/提交及owner隔离。多片段新增用例为纯算法层，不声明多片段HTTP链新验收。API契约保持原指纹。方案及命令见上方链接。

S03本切片已修复；此前“未修/xfail”为历史阶段。S05/S07及其余N行不因此关闭；未全量/移动端/真机验收，无APK，改动留本地。


## 2026-11-09 S05/S06 回归与最小方案（未修复）

按用户授权新增`test_schedule_time_boundaries.py`共9项，冻结planning及schedule_drafts的时钟，不改变认证时钟。S05完全过去/跨now窗口×两个入口共4项错误给过去建议；S06生成后仅推进时钟，数据库快照不变，仍实际写入2条日程，2项失败。省略起点两个入口及未来提交/晚到幂等重试共3项通过。

首次6 failed、3 passed；限定专用异常strict xfail后与S03等合跑45 passed、6 xfailed、5 warnings。S06从N更新为已复现P，未修复；Q08拒绝或调整仍待决。[定位与最小方案](../../superpowers/plans/2026-11-09-rf043-s05-s06-time-boundaries.md)包含原有固定历史日期测试的时钟兼容步骤。

本轮未新增生产逻辑修改，保留S03已有未提交修复；未全量/移动端/真机测试，无APK，不提交/推送。


## 2026-11-09 S05/S06 局部修复（最新）

用户确认过去起点直接拒绝、过时草案整份拒绝。时间测试18项无xfail，相关排程及review_api共66 passed、5 warnings；OpenAPI结构指纹不变，API文档补充422/409 DRAFT_EXPIRED行为。旧历史日期测试只冻结排程时钟，认证不受影响。

S05/S06本切片已修；上述预期失败为前阶段历史。S07及其他公共契约待决仍开放；无全量/移动端/真机验收，无APK，不提交/推送。


## 2026-11-09 S07 时区回归与定位（未修复）

新`test_schedule_deadline_timezone.py`共11项：两项纯日期UTC建议提交失败；纯日期双方截止之前、明确offset等价/精确截止、剩余不足30分钟及手动Task无offset输入拒绝共9项对照。冻结排程时钟，实际HTTP和合成Evidence；初次2 failed/9 passed，相关合跑75 passed、2 strict xfailed、5 warnings。

根因是预览排序/紧迫度/可排窗口使用请求timezone解释纯日期，提交与review重新确认则固定Asia/Shanghai。推荐沿用既有写入口径统一预览，Q08纯日期策略仍待确认。见[最小方案](../../superpowers/plans/2026-11-09-rf043-s07-deadline-timezone.md)。本轮未改生产逻辑，S03/S05/S06修复仍通过；未提交/推送，无APK。


## 2026-11-09 S07 局部修复（最新）

用户确认纯日期按上海当天23:59:59，明确offset保持绝对时刻。新增共享task_deadline helper统一三个预览点及提交；请求工作timezone不变。S07从11项扩至21项，移除xfail；加review_service精确边界两项，相关回归99 passed、5 warnings。旧不合法草案仍拒绝，前两项修复保持通过。

此前S07未修/xfail为历史状态；本切片已修复，未全量/DST/真机验收，无APK，未提交或推送。
