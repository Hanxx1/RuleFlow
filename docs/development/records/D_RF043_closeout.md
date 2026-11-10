# RF-043 修复证据与页面恢复检查

核对日期：2026-11-09。源码基线 `d8672de`，工作分支 `fix/RF-043-scheduling-consistency`，叠加当前未提交修复。本记录包含先前诊断与后续授权修复；页面业务改动仅 PlanSchedule.vue，新增真实API移动恢复回归。所有修改仍未提交/推送。

## 当前结论

三项后端修复和页面恢复切片均已完成本地验证：后端全量223 passed、5 warnings；前端96 passed；vue-tsc/Vite构建通过。390×844 Chrome触控＋真实本地API恢复链8个检查通过，包括过时拒绝、重新预览、网络失败重试及已提交响应丢失后幂等。团队签认、原生真机与RF-043其他未决语义仍未验收，不标整卡完成；本轮无APK。

最新页面证据见文末“授权修复与真实恢复链”；下方原页面检查保留为修复前历史。

## 失败到通过的证据索引

| 切片 | 原始缺陷及失败证据 | 当前修复与测试入口 |
|---|---|---|
| S03 前置耗时不足 | 预览只看前置结束时间，提交累计耗时；历史复现/实施记录见样例矩阵文末S03两节 | `server/tests/test_schedule_predecessor_duration.py` 18项；30/90、89/90阻断，多片足量、缺元数据、owner隔离、done/skipped兼容、旧非法草案拒绝 |
| S05/S06 过去窗口/过时草案 | 历史首次6 failed、3 passed：过去起点获建议，时间流逝后草案仍写入 | `server/tests/test_schedule_time_boundaries.py` 18项；过去起点422，省略起点取服务器now，过时整份409 DRAFT_EXPIRED、零写入、pending不变，已提交晚到重试幂等 |
| S07 截止时区 | 历史首次2 failed、9 passed；扩大样例后RED 7 failed、12 passed | `server/tests/test_schedule_deadline_timezone.py` 21项＋review精确边界；统一上海纯日期，保留offset绝对时刻，排序/评分/工作日推进后再次检查latest |

历史RED数字引用已有记录，本轮没有撤回生产修复重跑RED。原始阶段记录和方案入口见 [样例矩阵](D_RF043_cases.md) 与 [工作记录](D_scheduling.md)。上述测试随下列完整命令重新执行；99项包含旧边界、提交、锁、课表、review等相关保护，不是全量后端。

```powershell
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests/test_schedule_deadline_timezone.py server/tests/test_schedule_time_boundaries.py server/tests/test_schedule_predecessor_duration.py server/tests/test_schedule_boundaries.py server/tests/test_schedule_drafts.py server/tests/test_schedule_splits.py server/tests/test_schedule_preferences.py server/tests/test_schedule_series_locks.py server/tests/test_client_calendar.py server/tests/test_review_api.py server/tests/test_review_service.py server/tests/test_manual_deadline.py -q -p no:cacheprovider --tb=short --disable-warnings
```

本轮结果：`99 passed, 5 warnings in 7.85s`，退出0。隔离测试数据库与合成资料，无真实账户/在线模型。

## 修复前页面检查：390×844 Chrome headless（历史）

历史诊断脚本（固定断言旧缺陷，修复后不作为通过门禁）：[rf043_ui_check.py](evidence/D_20261109/rf043_ui_check.py)。复用本机已有 D:/py 的 websocket-client；后端用仓库 review-venv，Vite用锁定依赖；没有新增依赖或改锁文件。每次使用随机端口、独立数据库/浏览器目录，结束终止所启动服务。命令：

```powershell
D:/py/python.exe -X utf8 docs/development/records/evidence/D_20261109/rf043_ui_check.py
```

本次本地证据目录：`.runtime/d-rf043-closeout/70fdfcc8/`（忽略目录，不提交），包含 `web-results.json`、`past-window.png`、`expired-draft.png` 与服务日志。脚本退出0表示成功观察并断言当前缺陷，不代表产品验收通过。

| 场景 | 检查方式及结果 | 恢复结论 |
|---|---|---|
| 普通预览→过去窗口422 | 真实登录、合成已确认事项、真实页面/HTTP；连续两次点击均422，显示“排程窗口起点不能早于服务器当前时间，请重新选择时间”，正式日程仍0条 | **未通过**：页面发送浏览器采样now，服务端收到时已过去；再次预览同样失败。排程预览没有窗口起点编辑器；上方课表预览起始日期只影响本机课表，不是此API窗口 |
| 过时草案409文案 | 用fetch响应替身提供草案与后端实际同结构DRAFT_EXPIRED响应，经过真实HTTP错误解包和Vue页面 | 文案“草案中的安排已过时，请重新预览”可见；旧预览保留、确认按钮恢复可点，重复确认发送第二次commit（替身），未在前端阻止无效重试 |
| 过时后重新预览 | 关闭草案响应替身，点击预览，真实后端仍返回过去窗口422 | **未通过**：错误更新为422，旧草案仍在，恢复被起点竞态阻塞 |
| 重新预览成功分支 | 恢复成功草案响应替身并再次预览 | 新草案请求完成、错误清除；只验证页面成功分支，不当成真实恢复链通过 |

草案过时UI使用响应替身，避免首个真实预览阻塞后完全无法检查页面；后端自然过时、事务和幂等由上述确定性回归覆盖。没有把二者拼成端到端验收。截图已查看，提示位于页面顶部、预览及确认位于下方；未做真实手指点击/自动滚动可达性验收。

## 修复前定位与最小修复建议（已获后续授权）

1. `mobile/src/features/planning/PlanSchedule.vue` 的 `makePreview` 每次发送 `window_start:start.toISOString()`；服务端 `planning.py` 严格比较服务器now。对于“从现在开始”的入口，优先省略起点，沿用后端已测试的服务器now默认行为；保留显式过去时间拒绝，不添加随意时间宽限。同步核对window_end和课表展开范围（跨日及最大范围）。
2. `confirmDraft` 的catch只写error，不按 `ApiError.code` 处理过时草案。收到明确DRAFT_EXPIRED时，应清除或禁用旧草案确认，并引导重新预览；不要对网络失败等未知结果一律清除，以保留幂等重试恢复。
3. 修复后增加移动尺寸回归：普通预览成功；过时后旧确认不可重复发送；重新预览成功后可确认新草案；网络失败后同草案幂等重试；课表变更/日期边界保持保护。届时再做真实API恢复链验收。

此前按“检查”范围定位并记录；以上UI业务修复已在下节实施。公共未决项仍引用 [唯一决策表](D_public_interface_questions.md)，不代签团队或更改其他成员计划。


## 2026-11-09 授权修复与真实恢复链（当前）

- `PlanSchedule.vue` 的“从现在开始”预览省略 `window_start`，由后端采样now。保留原window_end与课表展开范围、课表授权和revision传递；没有扩大到未展开的窗口，也没有放宽显式过去起点的422保护。
- 仅捕获真实 `ApiError.code === DRAFT_EXPIRED` 设置过时标记；旧建议仍可查看，但确认按钮禁用且handler也拒绝执行。错误提示设role=alert并提供“重新预览排程”按钮。新草案成功返回才清除标记；重新预览失败仍禁用旧草案。
- 网络错误不丢弃草案、不改draft_id，允许同草案再次确认；服务端幂等与事务逻辑未因本轮页面修复改变。切换事项时清除局部过时状态。

### 回归过程及命令

新增 [rf043_ui_recovery.py](evidence/D_20261109/rf043_ui_recovery.py) 为移动页面自动化回归，不依赖额外npm/Python安装。它复用真实应用、HTTP、独立SQLite、合成账户与通知确认链，Chrome 390×844，按钮使用CDP触控事件；确认弹窗由测试自动接受。测试专用ASGI包装器只替换planning/schedule_drafts时钟，认证仍用真实时钟；不向生产代码增加测试接口。

RED1：原页面首个真实预览返回422，`status==200`断言失败。仅移除起点后RED2：真实DRAFT_EXPIRED后“Expired draft confirm is still enabled”断言失败。加入过时状态后GREEN。最终加强回归：首次预览使用真实服务器时钟；随后按建议起点推进排程时钟，另加入重新预览网络失败检查；8个检查全部通过。

```powershell
D:/py/python.exe -X utf8 docs/development/records/evidence/D_20261109/rf043_ui_recovery.py
npm.cmd --prefix mobile test
npm.cmd --prefix mobile run build
.runtime/review-venv/Scripts/python.exe -X utf8 -m pytest server/tests -q -p no:cacheprovider --tb=short --disable-warnings
```

- 移动恢复回归：退出0，证据目录 `.runtime/d-rf043-ui-recovery/7b23fcbc/`，含 `web-results.json`、`expired-disabled.png`、`recovered.png`、服务日志与独立测试数据库。初次GREEN截图也位于 `88795be1/`，已查看过时提示/按钮状态。
- 8个检查：省略起点真实预览200；自然过时真实409且日程0条/草案pending；旧确认不可再次发请求；重新预览失败不恢复旧确认；真实重预览获得新draft_id；发送前断网保留草案且零写入；真实commit成功但响应丢失后仍保留草案；时钟推进后重试同draft_id返回 `idempotent:true`，2条日程ID完全相同，无重复写入。
- 没有替换任何成功/失败API响应；仅模拟传输失败（发送前、返回真实提交响应后）与推进排程时钟。不是外网/真实账户/物理设备验证；自动接受确认弹窗不等于人工验收。
- 前端19文件96 passed；vue-tsc与Vite生产构建退出0。Vite CJS Node API弃用警告仍存在。
- 后端完整 `server/tests`：223 passed、5 warnings，22.71秒，退出0。未为压过警告修改依赖或业务逻辑。

本轮没有新增依赖、迁移、公共API字段或改动其他成员业务。原三项后端修复和其他未提交文件保留；没有提交、推送或生成APK。
