# RF-043 S07 截止日期时区一致性最小修复 Implementation Plan

> **最新状态：2026-11-09 用户确认纯日期按上海当天23:59:59、明确offset保留原绝对时刻；已完成本地修复与99项相关回归，未提交/推送。** 下文保留历史定位证据，文末记录实施结果。

**Goal:** 同一任务截止不因排程显示/工作时区变化而改变；预览建议与提交保护采用同一绝对截止时刻。

**Architecture:** 建议保留当前提交与通知重新确认已执行的Asia/Shanghai纯日期口径，统一预览排序、紧迫度和可用窗口的截止解释。显式带offset的时间戳继续按其绝对时刻，不改工作时段所用的请求timezone。

**Tech Stack:** Python、FastAPI、SQLite、pytest；无新增依赖/数据库迁移。

**Spec:** [RF-043 S07](../../development/records/D_RF043_cases.md)、[Q08公共决策](../../development/records/D_public_interface_questions.md)。基线main `4144bdb`加本地S03/S05/S06修复，2026-11-09。

## 实施前测试与结果（历史）

`server/tests/test_schedule_deadline_timezone.py`共11项，使用真实HTTP、合成账户/Evidence与隔离内存库；局部冻结排程时钟到2098-12-31，避免S05/S06门禁干扰。

- 两项缺陷：deadline=2099-01-01、timezone=UTC，分别从17:00Z安排30分钟、从15:30Z安排60分钟。两者都有预览建议，未改变任务或日程就commit，均409“安排超出任务截止时间”；日程不变、草案pending/committed_at为空。第二项证明不仅起点，片段结束也必须受截止限制。
- 两项对照：纯日期但处于双方截止之前，UTC/Asia/Shanghai请求均可预览08:00Z并提交。
- 四项对照：明确截止08:30Z或等价16:30+08，输入均标准化为08:30Z；两种请求timezone都生成恰好截止时结束的30分钟建议并提交。
- 两项对照：明确截止08:29:59.999999Z，两种timezone均因不足30分钟阻断，正式日程无写入。
- 一项输入边界：手动创建Task的无offset时间戳被422拒绝，不能拿它当作该入口可达的正常任务测试。

首次运行2 failed、9 passed、5 warnings、退出1。两项均抛DeadlineTimezoneMismatch，先确认实际409原因及零写入，再明确标记strict xfail（仅捕获该专用异常）；设置/HTTP异常不能被吞掉。相关10个文件合跑75 passed、2 xfailed、5 warnings，退出0；原有66项仍通过。xfail不是修复或通过，后续移除标记。

测试刻意只锁定一致性，不抢先批准纯日期时区策略：如果没有建议，须有对应deadline类阻断；如果给建议，同一候选在无其他变化时应能提交。后续确认固定口径后，应收紧为具体UTC时刻与拒绝结果。

## 差异定位与数据流

1. `main.py::normalize_deadline`：手动Task输入的纯日期原样保存，带offset时间戳转换UTC，无offset时间戳拒绝。Task没有独立deadline_timezone字段。
2. `schedule.py::_deadline(value,tz)`：纯日期解释为给定tz当天23:59:59；明确offset转换时区但保留绝对时刻。对旧无offset值的fallback使用tz，本轮没有声称覆盖所有历史数据入口。
3. `preview_schedule`从请求timezone得到tz；`_sort_tasks`截止排序、紧迫度计算、最终latest窗口三处都按该tz调用_deadline。
4. `planning.py::validate_schedule_write`固定调用_deadline(value, Asia/Shanghai)，用片段ends_at与其比较，超过则409。
5. `services/review.py::confirm`重新确认已有任务截止时也按Asia/Shanghai检查已保存安排，不是只有提交端存在该口径。
6. 草案保存timezone，但提交不会据此改变任务截止；commit没有对应HTTP时区参数。这是不同调用点对纯日期解释不同，不是字符串格式、数据库UTC转换或S05/S06时间流逝问题。

具体例：2099-01-01按UTC为23:59:59Z，按Asia/Shanghai为15:59:59Z，相差8小时。截止含明确offset时两者绝对时刻一致。

## Global Constraints / 用户已确认决策

- 用户后续明确授权按本方案修复；保留前两项本地修复，不提交/推送。
- 用户已确认Q08本切片：沿用提交和重新确认已有的Asia/Shanghai当天23:59:59；请求timezone只影响工作日/工作时间及展示，不重解释任务截止。
- 不建议直接让提交相信草案timezone：这会使同一任务通过切换排程时区延后截止，并与手动安排/通知重新确认不一致。
- 此推荐是兼容当前存量行为，不声称所有校园通知都天然属于上海时区。若要支持任意来源时区，需独立存储截止时区、证据、确认与迁移，超出本最小切片。
- 保留当前23:59:59精度，不顺带改成23:59:59.999999；具体时刻截止按原offset尊重，不能截成日期或强制改其绝对时间。
- 不改任务排序权重、工作时段/DST算法、S03前置门禁、S05/S06过时门禁、事务、owner与Evidence规则。

## 最小实施步骤（已执行）

### Task 1：收紧目标与统一截止解释

**Files:** `server/app/services/schedule.py`、`server/app/api/planning.py`；测试新S07文件。

**内部接口建议：** 在schedule.py添加`task_deadline(value: str | None) -> datetime | None`，调用已有`_deadline(value, timezone_for('Asia/Shanghai'))`。返回带时区的datetime或None，不增加HTTP字段。保留通用_deadline供既有其他调用使用。

- [x] 确认上述固定口径；运行缺陷命令确认2项失败；将目标收紧为17Z不可排、15:30Z的60分钟不可跨截止，移除strict xfail。
- [x] 三个预览截止调用（排序、紧迫度、latest）统一使用task_deadline；不要把整个请求tz替换为上海，工作时间仍跟随请求timezone。
- [x] validate_schedule_write使用同一helper，保持原截止语义及409保护；不读取客户端提交的timezone来重解释Task。
- [x] 保留review.confirm已有上海口径，不扩大改动；补测试核验它与helper一致。无需修改数据库、Task模型、请求DTO或依赖。
- [x] 新生成草案拒绝超期候选，修复前已经存下的不合法草案提交仍须409且无写入；不能仅靠预览修复而删除提交门禁。

### Task 2：边界与兼容验证

**Files:** 新S07测试、已有schedule/review相关测试；API文档及D记录。

- [x] 增加纯日期helper明确映射15:59:59Z，以及恰好截止/超过1微秒的实际写入边界；保留明确offset等价与精确截止对照。
- [x] 补直接preview入口对照（本轮HTTP缺陷使用drafts，内部共享schedule_preview但未单独增加直接入口用例）。
- [x] 增加排序及紧迫度的可观察测试：混合纯日期/明确时刻，在UTC请求下按统一绝对截止排序/算分，不能只改最终窗口使仍按错误截止排序。
- [x] 用确认记录构造旧不合法草案测试，验证提交零写入及pending；补通知重新确认与既有日程冲突保护测试，不能在新helper引入后悄悄漂移。
- [x] 运行下方相关回归，并加review确认服务/任务独立截止相关测试；核验API契约与文档。原S03/S05/S06必须继续通过。
- [x] 在API文档明确区分排程timezone与任务纯日期口径，更新Q08本切片选择与D矩阵。用户当前禁止提交/推送，不自动执行。

## Review Focus / 未验证范围

本轮只覆盖UTC/Asia/Shanghai；DST切换、其他地区纯日期、混合截止排序/紧迫度、直接preview专门用例、旧无offset存量数据、旧草案直接写入边界和review重新确认的一致性留待实施验证。不能把本次手工Task输入拒绝结论泛化为所有导入或旧库入口。无全量/浏览器/移动端/真机测试，无APK。

## 复现命令

关闭xfail（历史2失败9通过；修复后该文件21项通过）：

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_deadline_timezone.py --runxfail -q -p no:cacheprovider --tb=short --disable-warnings
```

相关回归（历史75通过2预期失败；最终扩展回归99项通过）：

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_deadline_timezone.py server/tests/test_schedule_time_boundaries.py server/tests/test_schedule_predecessor_duration.py server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py server/tests/test_review_api.py -q -p no:cacheprovider --disable-warnings
```


## 实施结果（2026-11-09）

- schedule.py新增task_deadline统一调用既有上海口径，三个预览点（排序、紧迫度、latest）及planning提交校验改用该helper。工作时段继续使用请求timezone，未改review生产代码的同等既有口径。
- S07文件从11项扩至21项、移除全部xfail；修复前7失败12通过，包括真实错误候选、错误排序/分数和helper未实现。修复后该文件全过，另补review_service两项精确上海日期截止边界。
- 最终12个相关测试文件：99 passed、5 warnings、退出0；涵盖原S03/S05/S06、review API/服务、手动截止。运行命令为上方相关命令再加server/tests/test_review_service.py和server/tests/test_manual_deadline.py。
- 明确offset仍保持原绝对时刻；纯日期映射15:59:59Z；结束恰好相等允许、超出1微秒拒绝。旧UTC不合法草案仍409且pending/零写入；没有通过放宽提交保护来消除差异。
- OpenAPI基线指纹不变：aa40e470df16fa9b2143aa452c92dab9debaa18467e3b9a7694cbeb95df838ed。API文档及Q08局部用户决定已同步。
- Ruling: 用户当前明确指令确认本切片口径，覆盖上轮待确认状态；不扩大为Q08全部子项或团队全体签认。保留23:59:59精度、历史无offset fallback和请求工作时区，未实施来源时区迁移。
- 未运行全量、DST切换、其他地区、旧库迁移、浏览器/移动端/真机；无APK。全部变更留本地未提交/推送。


## 独立审查与补充修正

审查发现_first_slot将cursor推到工作时段起点后未重验latest：UTC14–20窗口、18–21工作时段、上海纯日期截止15:59:59Z仍返回18:00建议。此边界直接破坏本次预览/提交一致性，纳入最小修复。

新增preview/drafts两项HTTP回归，先2 failed，再在推进day_open后补充cursor+duration不得超过latest的检查。最终99 passed、5 warnings（S07文件21项），无xfail。未取消任何提交保护。其余截止调用点、明确offset和工作timezone保留经只读审查核对；审查未重跑整套回归，最终测试由主执行者运行。

Ruling: 额外修正工作时段推进后的截止门禁，因它可复现地破坏本次目标；范围仅增加一次同等上界检查，不改变工作时段策略。DST/设备边界仍未验证。
