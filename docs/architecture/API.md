# RuleFlow API

## 2026年11月2日独立隐私工具移除

提交 `b6c4984` 有意删除独立文字隐私工具的 `POST /api/v1/privacy/analyze` 及其专用请求模型 `PrivacyIn`。共享检测引擎、导入确认与文件隐私扫描/脱敏接口保留。

当前 OpenAPI 基准为 80 个路径，SHA256 为 `aa40e470df16fa9b2143aa452c92dab9debaa18467e3b9a7694cbeb95df838ed`（UTF-8、排序、紧凑 JSON）。[契约基准](../testing/api-contract.sha256)已同步更新；CI 继续严格比较完整 OpenAPI，不跳过差异检查。此前 81 个路径的重构前快照保留于历史基线记录中。

## 2026年10月14日知识资料增量

GET /api/v1/knowledge/documents列当前owner资料；POST /knowledge/text接受title/text/category/consent，POST /knowledge/documents接受file/title/consent。POST /knowledge/search、/knowledge/ask接受query/top_k/category，返回owner私有资料的真实片段/行定位。当前ask为extractive原文摘录，无命中RAG_NO_EVIDENCE，不调用模型记忆补答。

DELETE /knowledge/documents/{id}删除索引，保留原件及已有Evidence快照。POST /cases/{id}/knowledge/{chunk_id}/attach必须consent=true，用户确认适用后关联条款、抽取规则并使行动确认失效；跨owner404，重复关联幂等。Real模式不读取Demo corpus；尚无资料保持原unavailable原因以兼容旧调用。

## 2026年10月14日画像与资格增量

Profile及Case Fact值须符合shared/profile.schema.json。非法类型/范围/未知字段返回 `{detail:{code:'PROFILE_INVALID',message,fields}}`，不包含原值；整次提交拒绝，不部分保存。null表示未知，0排名保留；数字字符串不会自动转换。Case Fact只接受scope=case。

新增 `GET /api/v1/profile/meta` → `{revision,updated_at,source:'user_input',invalid_fields}`。revision按owner画像/事项事实变化递增。Case evaluate只读，返回eligibility_truth、所有硬规则结果、missing_profile_fields、failed_rule_ids、supporting_evidence与profile_revision。scope/eligibility合并AND，action_trigger不决定资格；无硬规则UNKNOWN。

模型候选可包含audience/submission/external_references的 `{value,inferred,evidence_ids,evidence_quotes}`；非空字段短引必须真实存在。rules.kind为scope/eligibility/action_trigger；action_trigger仅接受有明确可选语义的角色或加分项目触发。Task origin标document/suggestion，建议步骤由用户选择。Review candidate.analysis保存最新完整候选及profile_revision，仍需POST confirm，不自动执行。

## 2026年10月14日文档与行级证据增量

- `GET /api/v1/documents/{id}`：原件元数据与lines（id/line_number/page/text/locator/bbox/coordinate_space/page_width/page_height/confidence）。不返回本地路径或owner_id。
- `GET /api/v1/documents/{id}/content`：需access token的原件下载，attachment/no-store/nosniff。
- `GET /api/v1/documents/{id}/pages/{page}`：需access token的PNG预览；图片仅第1页，PDF按实际页码；不支持的格式提供文字定位。
- `DELETE /api/v1/documents/{id}`：只删除当前owner未关联来源或证据的原件；被引用时返回DOCUMENT_IN_USE。

Case resources的Evidence可附document_id/line_id/bbox/coordinate_space/page_width/page_height/ocr_confidence/preview_available。旧Evidence没有坐标则保持原值，不伪造。新文件导入按行保存证据；sources/files的metadata与旧imports/files响应附document_id。

文件限制：图片10MB/2000万像素，其他文件20MB，PDF20页且每页OCR渲染预算2000万像素；Office展开最多64MB/10000个ZIP条目。FILE_UNSUPPORTED/FILE_CORRUPTED/PDF_TOO_MANY_PAGES/PDF_PAGE_TOO_LARGE/OCR_EMPTY等错误不含原文。解析失败的有效原件保留为failed，用户可授权读取或删除。

所有私有接口使用 `Authorization: Bearer <access token>` 并强制按 `owner_id` 过滤；响应统一为 `{data, request_id}`。

## 账号

- `POST /api/v1/auth/register|verify|login|refresh|logout`
- `POST /api/v1/auth/password/reset-request|reset`
- `GET /api/v1/auth/sessions`
- `DELETE /api/v1/auth/sessions/{id}`：撤销当前 owner 的指定设备会话
- `GET|PATCH /api/v1/account/settings`：显示名称、locale 与 timezone
- `GET|PUT /api/v1/profile`
- `GET /api/v1/profile/completeness`：从当前 Profile 与当前 owner 已有规则实际引用的字段动态计算完整度

## 事项、规则与计划

- `GET|POST /api/v1/cases`，`GET|PATCH /api/v1/cases/{id}`
- `GET /api/v1/cases` 支持 `q`、`status`、`category`、`deadline_from`、`deadline_to`、`sort`、`limit`、`cursor`；列表动态返回 `task_count`、`done_task_count`、`progress`
- `GET /api/v1/cases/{id}/resources`：effective facts、Evidence、Rule AST、tasks、materials、conflicts 与 evaluation
- `PUT /api/v1/cases/{id}/facts`，`GET /api/v1/cases/{id}/evaluate`
- `POST /api/v1/cases/{id}/tasks|materials|edges`，`PATCH /api/v1/tasks/{id}`
- `GET /api/v1/cases/{id}/plan|export.txt|export.ics`；Plan 返回动态 `overall_progress`、`current_tasks`、`completed_tasks`、`pending_tasks`

Task DTO 包含 `duration_minutes`、`deadline`、`materials`、`files`、`is_actionable`；`is_actionable` 由 DAG 前置任务状态计算。手工更新 Case deadline 时记录 `deadline_source=user_input` 并生成用户填写Evidence；明确不代表官方文件，同时使已有分析确认失效。

## 分析候选与用户确认 2026年10月14日

- `GET /api/v1/cases/{id}/reviews`：返回 `{revision,status,candidate,decision,confirmed_at}` 或null，GET只读。
- `POST /api/v1/cases/{id}/reviews/prepare`：用户主动载入旧步骤/证据核对，保留原任务ID，幂等。
- `POST /api/v1/cases/{id}/confirm`：`{revision,action_ids,deadline_id?,manual_deadline?,no_deadline,consent}`，consent必须true，截止候选/人工日期/不设截止三选一。

candidate包含actions/dates：action有id/title/evidence_ids/evidence_quotes；date有id/raw/value/role/quote/evidence_ids/review_reasons，role为publication/event/deadline/unknown。缺年份或含尚不支持的具体时刻时value=null，不自动采用。正式任务仅在确认后生成，不按候选顺序自动加依赖。

错误使用现有 `{detail:{code,message}}`：CONFIRMATION_REQUIRED、REVIEW_REQUIRED、REVIEW_STALE、REVIEW_INVALID、REVIEW_ALREADY_CONFIRMED、REVIEW_TASK_SCHEDULED、EVIDENCE_INVALID。相同选择重复确认不重复生成任务，错误事务回滚，UNKNOWN保持UNKNOWN。Task新建/状态修改、预览与task日程写入受确认门禁保护；日程写入事务内复核。

相关性结果通过 `reason` 区分 `missing_profile_fact`、`missing_case_fact`、`insufficient_evidence` 与 `rule_unknown`，并分别返回缺失字段；Profile 更新后会重新计算当前 owner 已有 Case。

## 日程安排

- `GET /api/v1/schedule`：支持 `from`、`to`、`case_id`、`task_id`、`kind`
- `POST /api/v1/schedule/items`
- `PATCH|DELETE /api/v1/schedule/items/{id}`
- `POST /api/v1/schedule/preview`：根据任务时长、截止时间、DAG 和已有 busy/course/task block 生成确定性建议

Preview 只读，建议须再通过 `POST /api/v1/schedule/items` 确认后才持久化。

## 工作台

- `GET /api/v1/dashboard`：返回当前 owner 的 `total_cases`、`in_progress_cases`、`due_soon_cases`、`completed_cases`、`recent_cases` 与 `today_tasks`

统计直接由 Case、Task 与 Schedule 当前状态聚合，不维护统计副本。`today_tasks` 合并账户时区内今日截止和今日已排程任务，并按 Task ID 去重；同时返回 `date` 与 `timezone` 作为展示口径。

## 知识条款

- `GET /api/v1/cases/{case_id}/knowledge-evidence`

Demo mode 使用可替换 Knowledge Provider 读取脱敏条款；`quote` 来自源 fixture，`confidence` 为 `null`，匹配程度使用 `match_type/match_score`。Real mode 未配置 Provider 时返回 `unavailable`，不读取 Demo fixture。

## 材料库

- `GET|POST /api/v1/vault/items`
- `GET|PATCH|DELETE /api/v1/vault/items/{id}`
- `GET /api/v1/vault/items/{id}/content`

Metadata 与文件内容分离保存。POST 使用 multipart，包含 `file`、`name`、`category`、JSON 数组字符串 `case_ids/task_ids`。内容路径不出现在 DTO 中；私有内容读取同样需要 access token。

## 隐私分析


该接口不持久化原文或 findings，也不将敏感原文写入日志。

## 导入与分析

- `POST /api/v1/import-batches`，`GET /api/v1/import-batches/{id}`
- `POST /api/v1/import-batches/{id}/sources/text|url|files`
- `DELETE /api/v1/import-batches/{id}/sources/{source_id}`
- `POST /api/v1/import-batches/{id}/analyze`
- `POST /api/v1/imports/text|files|url`
- `GET /api/v1/imports/{id}/progress`
- `POST /api/v1/imports/{id}/cancel|retry`

ImportBatch 可同时保存文字、URL 和文件来源。每个来源独立记录 `ready/completed/failed`、错误、metadata 与 EvidenceRef；analyze 按 revision 幂等，同一 revision 不重复生成 Case、Task 或 Evidence。GET 只根据 analyze 保存的时间点投影 `queued/processing/completed/partial_failure/failed`，不修改数据库。

URL 导入拒绝本机、private、loopback、link-local 和 reserved 地址，对每次跳转重新做 DNS/IP 及连接端点校验；本地代理的 RFC 2544 synthetic DNS 只在代理实际接管域名连接时识别。URL 错误使用 `url_dns_failed`、`url_unsafe_address`、`url_timeout`、`url_http_error`、`url_content_too_large`、`url_content_parse_failed` 等结构化 code。文件最多 10 个、单个最多 20 MB。只有明确 `consent=true` 后才解析和持久化来源。旧 `/imports/*` 接口继续兼容。

## 同步与 Demo

- `POST /api/v2/sync/push`：`operation_id` 幂等、版本冲突与 tombstone
- `GET /api/v2/sync/pull?cursor=`：游标增量读取
- `GET /api/v1/demo/notices/assessment`：只读脱敏回归示例

开发环境会返回一次性验证/重置 token。生产环境字段为 `null`，需要接 SMTP 投递。

## 2026-10-14 后续阶段接口（migration010–016）

- POST /api/v1/documents/{id}/privacy/scan：返回revision、masked findings、bbox、heuristic风险与unsupported_types。二维码不解码。
- POST /api/v1/documents/{id}/redact：{revision,finding_ids,consent:true}，返回副本id/hash，原件不变；无坐标拒绝。
- GET /api/v1/document-copies/{id}/content：owner授权下载，无缓存；PDF文字层及选中区域永久移除。
- POST /api/v1/schedule/drafts：同preview输入，新增preferences {work_start_hour,work_end_hour,buffer_minutes,daily_max_minutes}；返回draft_id/suggestions分段/unscheduled。
- POST /api/v1/schedule/drafts/{id}/commit：{consent:true}；数据变化时409 DRAFT_STALE；待提交草案任一片段开始时刻早于本次事务采样的服务器now时409 DRAFT_EXPIRED（草案中的安排已过时，请重新预览），在首条写入前整体拒绝，保持pending及原日程；成功后重复提交仍幂等。
- POST /api/v1/schedule/preview 与 /drafts：window_start早于本次请求采样的服务器now时422（排程窗口起点不能早于服务器当前时间，请重新选择时间），不自动调整、不创建草案；相等允许，省略起点使用同一now。所有比较按带时区的绝对时刻。空建议草案沿用无日程写入语义，不使用创建年龄作为TTL。
- PUT /api/v1/tasks/{id}/planning：{duration_minutes,splittable,min_chunk_minutes,max_chunk_minutes,importance,preference}；生成用户填写Evidence，已有安排先移除。
- POST /api/v1/schedule/series：ScheduleItem加count(2..13)、every_weeks(1..4)、timezone；仅course/busy，整体事务。
- POST /api/v1/schedule/items/{id}/lock：{locked:true|false}。锁定需解锁才能PATCH/DELETE；独立任务安排检查前置与deadline。
- GET /api/v1/cases/{id}/analysis-history：不可变分析revision/candidate/created_at，仅owner。
- GET /api/v1/cases/{id}/analysis-inputs：可重用的import id/name/kind，不暴露磁盘路径。
- POST /api/v1/imports/{id}/retry：现在必须{consent:true}，同步实际重试已保存Evidence；RETRY_SOURCE_MISSING/BUSY明确拒绝，不创建无人消费队列。
- POST /api/v1/import-batches/{batch}/sources/{source}/attachments：{index,consent:true}，候选URL按现有SSRF策略重新校验，返回child metadata.parent_source_id。解析前不自动抓附件。
- PUT /api/v1/profile：增加valid_until {字段:带时区ISO时间|null}，仅本次facts字段可设置。
- PUT /api/v1/cases/{id}/facts：可附valid_until；过期字段按UNKNOWN缺失处理。
- GET /api/v1/profile/meta：新增field_valid_until/expired_fields。
- GET /api/v1/profile/history：最近500条本账户填写断言，原始替换值可追溯。
- GET/PUT /api/v1/profile/interests：{categories:[合法Case分类]}，软偏好独立于AST画像字段；evaluate返回relevance_level/interest_match/interest_evidence_ids。
- POST /api/v1/vault/items：现在Form consent=true必需，所有上传有流式20MB读取上限。

迁移编号实际为006–016，不使用早期方案中的预估编号。在线使用需要部署对应后端；调试APK不内置私有密钥。
# 2026-10-14 语义校验补充

分析候选增加 `unsupported_conditions`（带 EvidenceRef 的 SemanticField 列表）。无法映射到共享画像字段的原文资格条件必须保留核对提示；它们不能转成任意 `exists` 或不相关数值规则。整体资格评估存在未建模条件时，原 TRUE 降为 UNKNOWN，FALSE 保持 FALSE。模型响应中的规则需通过原文证据及局部语义校验后才能执行。

`POST /api/v1/cases/{id}/confirm` 新增可选 `task_deadlines`：`{"action:0":{"deadline_id":"date:1"},"action:1":{"manual_deadline":"2026-12-02"},"action:2":{"no_deadline":true}}`。每个键必须是所选行动ID，每项只能选择一种处理方式；未指定的任务沿用事项日期。人工日期创建用户确认证据，不冒充官方时间。重复提交须包含相同选择。

Profile新增 `moral_score`（0–100数值）、`advisor_count`/`participation_count`（0–100整数）、`disciplinary_status`（clear/recorded）、`coursework_status`/`fitness_status`（passed/failed），均可null并遵守共享Schema。用户自述不等于官方资格证明；缺值保持UNKNOWN。

# 客户端资料与课表接口

新客户端画像默认保存在IndexedDB，结构版本2；`school`加入共享画像和AST白名单。表单、补充原文、确认资料卡、适用范围、有效期、历史、课表与关注分类按客户端owner分区。读写采用版本检查，不能覆盖另一页面刚保存的资料。退出登录清理当前账户本机资料。旧Profile API保留兼容，新客户端不自动PUT画像，也不自动提交补充原文。

`POST /api/v1/timetable/parse`：multipart `file`、`consent=true`。登录和明确确认后进行有界文件解析，返回待核对文字，原件不保存，不自动加入课表。

`POST /api/v1/schedule/drafts`增加 `calendar_blocks`（id、starts_at、ends_at、evidence_ids）、`calendar_consent`与`calendar_revision`；只在同意后发送占用时段，不包含课程名称。客户端本机版本与草案保存时版本须一致。`POST /api/v1/schedule/drafts/{id}/commit`增加 `calendar_revision`，并检查已确认课程与任务建议不重叠。

`GET /api/v1/cases/{id}/resources`增加附件清单、缺失数及状态，规则返回kind，供客户端排除可选动作规则。文件名称匹配不等于内容已审核。

`POST /api/v1/cases/{id}/attachments`：multipart `file`、`consent=true`，只允许当前owner事项，添加附件及上传记录并使旧确认失效。

`POST /api/v1/cases/{id}/analysis/retry`：`{"consent":true}`，使用该owner事项的已保存正文及附件证据，保留历史及任务状态，返回新的待确认候选。动态网页附件只记录发现和来源，不自动获取；网络返回HTML而非附件时必须提示补充文件。

迁移017/018分别增加case_attachment_documents与case_attachment_links；按owner隔离，Demo重置也清理这些关系。


### 排程任务截止口径（2026-11-09）

纯日期Task.deadline统一按Asia/Shanghai当天23:59:59解释；明确带时区时间戳保留原绝对时刻。排程请求timezone用于工作时段及展示，不延长或缩短任务截止；预览截止排序、紧迫度、可排窗口及提交保护采用同一口径。安排结束等于截止可接受，晚于截止拒绝；旧不合法草案提交仍409且不写入。本变更不修改截止存储格式或HTTP结构。
