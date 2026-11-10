# RF-043 S05/S06 过去窗口与草案自然过时最小修复 Implementation Plan

> **最新状态：2026-11-09 用户确认直接拒绝过去窗口、整份拒绝过时草案，已完成本地修复与66项相关回归；未提交/推送。** 下文保留实施前复现证据，文末为实施结果。

**Goal:** 不生成可保存的过去安排；待提交草案在时间流逝后出现已开始的片段时，整份拒绝且零写入。

**Architecture:** 在HTTP预览入口检查服务器当前时间；在草案提交事务内、首次写入前检查所有片段开始时刻。算法保持显式输入的纯函数，状态指纹不包含不断变化的时间。

**Tech Stack:** Python、FastAPI、SQLite、pytest；测试以monkeypatch冻结排程模块时钟，无新依赖。

**Spec:** [RF-043 S05/S06](../../development/records/D_RF043_cases.md)、[Q08公共决策](../../development/records/D_public_interface_questions.md)。基线main `4144bdb`加本地S03修复，2026-11-09。

## 实施前测试与证据（历史）

新文件 `server/tests/test_schedule_time_boundaries.py` 共9项：

| 场景 | 测试输入 | 当前结果 |
|---|---|---|
| S05 完全过去窗口 | 服务器12:01，指定08:00–12:00；preview/drafts各一项 | 仍返回08:00建议，2项失败 |
| S05 跨当前时刻窗口 | 服务器08:15，指定08:00–12:00；两个入口 | 仍返回08:00建议，2项失败 |
| S06 首片已开始 | 07:59生成08:00/08:30两片，服务器推进到08:00:01 | commit 200，真实增加2条日程，草案committed，1项失败 |
| S06 首片已结束 | 同草案，服务器推进到08:31 | 同样真实写入2条日程，1项失败 |
| 省略开始时间 | 服务器08:15，两个入口不传window_start | 采用08:15起点，建议08:30，2项通过 |
| 未来提交＋晚到重复请求 | 07:59提交08:00草案，12:01重试 | 首次写入1条，重试幂等且不重复写入，1项通过 |

- 初次未标记运行：6 failed、3 passed、5 warnings，退出1，六项均在专用PastScheduleAccepted异常处失败。
- 最终只对上述六项标记strict xfail，且限定raises=PastScheduleAccepted。环境、账户、HTTP准备或其他断言失败不会被该标记吞掉；修复后XPASS会失败提醒移除标记。
- 相关8个文件合跑：45 passed、6 xfailed、5 warnings，退出0；原S03的42项仍通过。xfail不等于问题修好。
- S06明确验证created_at为冻结时间、提交前数据库snapshot哈希与草案一致。变化只有排程服务器时间，不修改任务或日程，因此不是用数据变更导致DRAFT_STALE冒充自然过时。
- 仅替换planning.datetime与schedule_drafts.datetime，认证时钟保持真实，避免令牌意外过期；使用内存数据库、合成账户与临时文件目录，没有真实用户数据或模型调用。

## 定位结果

1. `server/app/api/planning.py::schedule_preview`第186–190行取得now，但仅在未传window_start时使用它；显式起点没有和now比较。
2. `services/schedule.py::preview_schedule`只验证终点大于起点和最多90天，搜索从window_start开始，不接触服务器now。这一纯算法职责可以保留，检查放API边界。
3. `services/schedule_drafts.py::snapshot`只哈希任务、依赖、日程、核对和偏好等表。单纯时间流逝不会变更hash；把now塞进hash会使几乎所有草案立即过时，不可取。
4. `commit_draft`在第43–47行处理已提交幂等、快照变化，再取得now字符串用于写入时间戳。没有将片段开始时刻和now比较。
5. `validate_schedule_write`检查权限、依赖、截止、冲突等，没有当前时刻门禁。新增校验不宜放这一通用函数，否则会顺带改变手工历史日程的录入/编辑语义。

## Global Constraints 与待确认决策

- 用户后续授权按本方案修复，明确选择过去窗口直接拒绝、草案过时整份拒绝；保留S03本地修复，不提交、推送或发布。
- Q08本切片已由用户明确选择拒绝策略；其他时区/纯日期/版本和留存问题未因此签认。测试现已收紧为422/409，不再接受自动调整。
- 实现显式window_start < server_now时返回422，提示重新选择时间；不静默修改窗口。省略起点沿用当前now；start==now允许，测试以冻结时钟验证。
- 实现待提交草案任一片段starts_at < server_now时返回409，code为DRAFT_EXPIRED并提示重新预览；错误码/文案按用户授权的本方案落地并登记API文档。无自动重排，无部分保存。
- 以服务器采样的一次aware UTC时刻为准，不信任客户端now，不以草案创建多久设置任意TTL。只要全部片段尚未开始，年龄本身不应使草案失效。
- 已committed的请求在权限/确认及既有校验之后，保持原有幂等返回；不要因时间已过把成功提交改判失败。
- 不改变手工历史日程、S07纯日期截止、skipped、耗时估计、草案取消留存；无数据库迁移、依赖或请求字段变更。

## 最小实施步骤（已执行）

### Task 1：过去窗口的API门禁

**Files:** `server/app/api/planning.py`、`server/tests/test_schedule_time_boundaries.py`。

**Interface:** 保持SchedulePreviewIn及HTTP返回包络；使用schedule_preview已有局部now。

- [x] 确认Q08拒绝方案及422错误语义。先运行下方缺陷命令确认六项仍失败。
- [x] 在时间解析完成后、算法调用及草案写入前，比较window_start与本次已采样now；推荐拒绝显式过去起点。不要引入第二次now读取，避免省略起点立即被自己的时间检查拒绝。
- [x] 复用同一schedule_preview，使preview和drafts一致；拒绝后不能残留schedule_drafts记录。
- [x] 将S05测试收紧为已确认的行为，移除对应xfail；补start==now、过去1微秒、UTC与+08:00等价时刻测试，验证不能因字符串时区不同绕过。

### Task 2：提交前的整份时间检查

**Files:** `server/app/services/schedule_drafts.py`、新增时间测试文件；保持通用validate_schedule_write不变。

**Interface:** commit_draft签名不变，使用现有DraftError包络，错误code按确认结果。

- [x] 在幂等分支和snapshot校验之后、第一条INSERT之前，取一次aware UTC now并逐项比较starts_at。任一片段已开始即抛DraftError，不能只比较window_end或最后一片。
- [x] 同一now也用于created/updated提交时间戳；判定按事务内采样瞬间，不逐条读取墙钟，不引入后台定时器。
- [x] 拒绝后所有正式日程不变、草案pending且committed_at为空；保留原来的权限、consent、calendar_revision、快照与事务校验。
- [x] 移除S06的xfail；补“列表首项未来、后项已过时”用例及已有正式安排的保护，确认与建议列表顺序无关、零部分写入。
- [x] 补未来但很早创建的草案仍可提交、相等时刻规则、空建议草案保持原有无写入语义；保留晚到幂等重试正例。DRAFT_EXPIRED已同步API错误说明。

### Task 3：测试时钟兼容与验证

**Files:** `server/tests/test_schedule_drafts.py`、`server/tests/test_schedule_splits.py`及其他搜索发现使用历史日期的HTTP排程用例；按需抽取test helper。

- [x] 搜索全部HTTP preview/drafts/commit测试；当前至少上述两文件使用2026-10-20固定日期。对需要成功排程的测试局部冻结排程时钟至其窗口之前，不删除断言、不修改认证时钟、不将时间校验关闭。
- [x] 保留纯算法的历史时间输入；它没有墙钟依赖，不需要批量改日期。S05/S06单独控制时间，不能被全局自动fixture掩盖。
- [x] 跑新增时间测试与下方全部相关排程回归，确认S03、事务回滚、owner/consent和幂等不退化；检查OpenAPI基线及错误码文档是否需要按确认结果更新。
- [x] 回写矩阵和D记录，分清已修与未测。用户当前要求不提交/推送，后续也不可自动执行。

## Review Focus / 本轮未验证范围

时区等价/微秒边界、过时片段位于列表后部、保留已有日程、空草案、较老但未来的草案均已补测通过。没有浏览器/Android/设备验证；没有APK；未跑全量后端。S05/S06已完成本切片修复；S07仍开放。

## 复现命令

关闭xfail暴露缺陷（历史6失败3通过；修复后该文件18项全部通过）：

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_time_boundaries.py --runxfail -q -p no:cacheprovider --tb=short --disable-warnings
```

相关回归（修复后基础排程60通过；加入review_api共66通过）：

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_time_boundaries.py server/tests/test_schedule_predecessor_duration.py server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py -q -p no:cacheprovider --disable-warnings
```


## 实施结果（2026-11-09）

- `planning.py`解析时间后使用原有单次采样now：window_start < now时422；相等允许，省略起点仍使用同一now。
- `schedule_drafts.py`在幂等和快照校验之后、第一条写入前采样UTC now；任一starts_at < now即409 DRAFT_EXPIRED，保持pending/committed_at为空。创建年龄、窗口结束和空草案不作为任意TTL依据。
- 时间测试扩至18项，移除全部xfail；先运行10 failed/8 passed，修复后全部通过。相关8个排程文件＋review_api共66 passed、5 warnings、退出0。测试包含过时片段放列表最后且逐项validator调用次数为0，证明整份预检查，而非依赖写后回滚补救。
- 新增schedule_clock.py，仅供显式选择的测试使用；旧drafts测试模块及splits中一项HTTP用例冻结至2026-10-20 07:59，保留原日期/断言，不触碰认证时钟、不更改全局autouse fixture。
- OpenAPI契约仍匹配指纹aa40e470df16fa9b2143aa452c92dab9debaa18467e3b9a7694cbeb95df838ed；结构不变不代表没有行为变化，422/409新增时间拒绝语义已登记API文档。
- Ruling: 用户本轮指令确定本切片拒绝策略，覆盖旧计划的“尚未确认”；不将其扩展为Q08所有子项或团队全体签认。
- Ruling: 沿用现有事务内单次服务器时间采样定义过时；不承诺事务执行期间每一微秒重新判定，不新增容忍窗口或后台失效器。已有幂等请求不会因时间流逝而误拒绝。
- 未运行全量后端、浏览器/移动端/真机，不构建APK；S03已有修复保留，所有改动本地未提交、未推送。

## 独立审查

只读审查未发现Critical/Important问题，确认过去起点门禁、微秒/时区比较、整份提交预检查、晚到幂等、owner/consent及事务保护。审查未独立重跑测试。DST切换、真实并发锁等待及设备/UI未验证。

Ruling: 手动新增/编辑历史日程继续保持既有语义，本次授权限定预览与草案提交；代价是不能把该修复宣称为所有历史日程入口的统一禁止规则。

最终文档本地链接检查164处通过，git diff --check通过；未提交、未推送。
