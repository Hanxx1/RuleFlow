> 当前状态以本页矩阵和最新阶段记录为准；早期阶段记录保留作历史，旧APK哈希已被后续产物替代。

# 智能识别子功能与独立验收计划

2026年10月14日。每项冻结输入/输出、失败状态和测试入口；独立测试使用fixture或FakeProvider，集成测试再验证连接。状态只代表所列范围，不能把确认UI当作完整图片理解或RAG完成。

| ID | 子功能 | 输入与输出 | 独立验收 | 当前状态 |
|---|---|---|---|---|
| S01 | 文件校验 | 字节流/MIME/文件名 → 已验证文件 | 伪装、损坏、体积/页数/像素预算 | 第二批补签名、Office展开预算、PDF页数/像素与分块读取 |
| S02 | 图片OCR | 图片 → 文字行/坐标/质量 | 固定图片与FakeOCR | 后端OCR、EXIF方向统一与行持久化已实现，端侧OCR待做 |
| S03 | PDF/Word解析 | 文件 → 文本行/表格/坐标 | 混合PDF、DOCX表格 | PDF原生/扫描/混合图片区域OCR、旋转坐标与DOCX表格已实现；复杂表格版面语义仍需核对 |
| S04 | 安全链接获取 | URL → 受限正文/状态 | MockTransport、DNS/重定向/超限 | 保留既有测试 |
| S05 | 附件关联 | HTML → 正文/附件/引用关系 | HTML fixture、用户单独同意 | 第七批附件候选、单项同意、父来源关系与原件保存已实现；不自动抓附件 |
| S06 | 文档证据存储 | 原件/行 → 稳定ID、授权预览 | 临时目录/SQLite、越权/删除 | 文件及网页原件、稳定行、授权预览/下载已实现 |
| S07 | 日期候选 | Evidence → 日期/语义/短引/原因 | test_date_candidates.py，纯函数 | 日期及明确时区的具体时刻候选已实现；缺年/时区不猜 |
| S08 | 行动候选 | Evidence → 原文动作/局部短引 | test_action_candidates.py，纯函数 | 本轮已实现保守规则 |
| S09 | 模型语义提取 | 文本行 → 固定Schema候选 | FakeLLM、非法Schema/引用/超时 | 固定Schema、局部引用、任务来源与保守显式依赖已实现；真实模型/多模态效果待配置验收 |
| S10 | 用户事实 | 类型化事实 → owner画像/版本 | 空值、类型错误、来源/时效 | 共享类型、owner版本、填写历史与显式有效期已实现；到期UNKNOWN |
| S11 | 资格及相关性 | AST+画像 → truth/原因/缺字段 | shared向量、无网络/模型 | 硬条件合并与三端源码语义已实现；有填写依据的软兴趣独立，不提升硬资格 |
| S12 | 候选版本 | 已校验结果 → Review/revision | test_review_service.py，独立SQLite | 最新候选及不可变分析历史已实现；确认/失效事件另有审计 |
| S13 | 确认门禁 | revision/选择/同意 → confirmed或拒绝 | ReviewService单测+ReviewAPI集成 | 本轮已实现 |
| S14 | 任务编译 | confirmed动作 → 幂等Task/材料关联 | 未确认0任务、重复确认、旧ID保留 | 稳定行动ID、幂等Task、旧步骤保留/取消核对、材料关联与用户耗时设置已实现 |
| S15 | 依赖DAG | 行动关系 → 有依据的DAG | 环、越权、并行、Fake模型边 | 原文明确前后依赖及人工依赖附Evidence；确认前环检测；不猜数组顺序 |
| S16 | 知识入库 | 资料 → 条款/版本/索引 | 文档fixture、FakeEmbedding | 第四批真实文本/文件入库、行引用分块已实现 |
| S17 | 知识检索回答 | 查询/owner → hits/引用结论 | 无命中、虚构引用、越权 | 第四批owner过滤的词项向量检索与原文摘录已实现；神经Embedding/生成式回答待配置 |
| S18 | 计划预览提交 | confirmed任务/占用 → 草案/冲突/日程 | 排程回归+门禁专项 | 分段、权重优先级、缓冲、每日限额、周期课、锁定、不可变草稿与原子提交已实现 |
| S19 | 隐私检测 | 文本行/图像 → Findings/不支持范围 | Regex/OCR fixture | 上传前Guard、文件行/二维码区域检测及明确不支持范围已实现；检测非安全保证 |
| S20 | 脱敏副本 | findings/选择 → 永久脱敏文件 | 原件hash、残留、越权/缺坐标 | 图片/PDF选区永久脱敏副本、原件不变、文字层移除、owner与版本校验已实现 |
| S21 | 证据确认UI | DTO/操作 → 展示/请求状态 | review.test.ts、移动浏览器脚本 | 确认UI及图片/PDF行区域高亮已接入测试 |
| S22 | 真实进度重试 | job → 实际stage/state | Fake执行器、恢复、GET只读 | Real同步真实结果、重试消费授权证据、取消前持久化门禁、历史已实现；无可靠异步队列声明 |

## 第一批实施边界

本轮实施S07/S08/S12/S13/S14的最小闭环与S18/S21连接，没有新增生产依赖。

1. 分析不直接创建正式Task，也不把首个日期写成最终截止。材料/规则仍是可查看的分析结果，资格不足保持UNKNOWN。
2. migration006 `case_reviews`保存候选/revision；`review_events`只审计动作与ID，不审计上传全文。候选快照当前保留最新版本，完整多次分析历史另做。
3. 日期区分publication/event/deadline/unknown；缺年、日期无效、多个截止、用途不明均提示。含具体时刻暂不归一化，不会自动把下午5点当成当天结束。
4. 用户选择已有动作，明确同意后在SQLite写事务中生成正式任务。相同确认幂等，不同选择或过期版本拒绝。用户可明确暂不设截止，此时不承诺截止前完成。
5. 不凭空生成“准备并提交”，不按动作列表顺序猜依赖；智能依赖尚未实现，人工边继续用已有受控接口。
6. 修改Case截止产生“用户填写、不代表官方文件”的Evidence，使旧确认失效。再次确认保留任务ID和完成状态；未选旧待办标skipped，已有日程的取消步骤须先移除日程。
7. 旧分析由用户POST reviews/prepare载入核对，保留原步骤ID/完成记录；GET不写数据。新建任务、状态更新、预览、task日程写入均检查确认；日程写事务再次检查确认/占用/唯一性。
8. Offline Demo入口和fixture未改；原有未提交改动保留。未自动提交Git或发布。

## 独立测试命令

server目录，使用项目既有Python：

```powershell
E:/DevTools/PythonPortable/python.exe -m pytest -q -p no:cacheprovider tests/test_date_candidates.py
E:/DevTools/PythonPortable/python.exe -m pytest -q -p no:cacheprovider tests/test_action_candidates.py
E:/DevTools/PythonPortable/python.exe -m pytest -q -p no:cacheprovider tests/test_review_service.py
E:/DevTools/PythonPortable/python.exe -m pytest -q -p no:cacheprovider tests/test_review_api.py
```

前三组无网络、模型或常驻后端；ReviewService用独立内存SQLite。API组用TestClient验证owner、版本、门禁、幂等与用户Evidence。

mobile目录运行 `npm test -- src/services/review.test.ts` 与 `npm exec vue-tsc -- --noEmit`。

移动测试：先启动 `npm run dev -- --host 127.0.0.1 --port 5193 --strictPort`，根目录运行 `scripts/test-review-mobile.mjs`。使用已安装Playwright和本机Edge；设置 `ZHISHI_BROWSER_MODULE_ROOT` 指向包目录，不新增仓库依赖。`ZHISHI_UI_TEST_ORIGIN`/`ZHISHI_TEST_BROWSER_CHANNEL`可调整环境。

移动脚本独立Mock API，分别验证360/390px：同意前禁用、缺年份不可直接选用、人工日期、过期版本拒绝、重读后重新同意、成功确认、无水平溢出。浏览器测试不等同Android实机验收。

## 阶段控制

每项顺序为：冻结契约 → 独立测试 → 实现 → 相关回归 → API连接 → 移动状态测试 → 更新文档。失败只修当前项，不换fixture冒充成功。每阶段记录可执行代码、测试、数据库迁移、限制与产物。

下一批S06/S02/S03先补原件/标准化行/原图高亮，再升级S09/S10/S11，随后接S16/S17真实知识检索。没有完成的项保持“待实现”。

## 第二批原件与行证据实施

migration007 `document_line_evidence` 新增documents/document_lines/evidence_lines/source_documents，保留旧Evidence表和ID契约。文件批次与旧文件导入入口均保存原件，再以每行建立Evidence。默认原件目录server/data/document_uploads已排除Git；DOCUMENT_UPLOAD_ROOT、DEMO_DOCUMENT_ROOT可配置，Demo/Real根必须相互不包含。错误码不记录上传正文。

图片坐标基于EXIF方向归一化后的图像，预览使用同一方向；原件保持字节不变。PDF原生文字逐行提取，旋转框转换到显示页坐标；扫描页OCR框按实际渲染尺寸换算到PDF point，预览按比例高亮。DOCX保留段落与表格行，文本类无坐标时只显示文字，不生成假框。

GET documents/{id}返回行；/content按owner提供原件下载；/pages/{page}返回授权PNG预览，Cache-Control=no-store，不在URL传token。DELETE只允许删除未关联来源/证据的原件；删除批次来源不会冒充删除原件，解除来源后可显式删除未使用原件。解析失败仍保留可授权读取/删除的Document。Demo reset清理该owner原件，不动其他owner或Real目录。

本批验证：全量后端79项通过，后续新增原件删除和Demo清理后文档专项10项通过；前端26项通过、类型检查通过；360/390px确认、授权原图、失败重试、缩放高亮、关闭及无横向溢出通过。没有新增生产依赖、真实模型或实机验收。后续继续S09/S10/S11，完整Privacy Guard、图片理解、真实RAG和复杂排程仍未完成。

独立入口：server目录运行 `pytest tests/test_document_lines.py` 与 `pytest tests/test_document_api.py`；前端运行 `npm test -- src/services/evidencePreview.test.ts`。PDF测试同时覆盖原生/扫描页、旋转及超大页面；API测试覆盖两类导入、无同意、越权、原件不变、解析失败保留和显式删除。

第二批最终APK为 `E:/ZhiShi/deliverables/Zhishi-RuleFlow-debug.apk`，10,252,499字节，SHA-256 `5011833D0E804F6B9543801D891118F8C6CC503CFD9C6477F8803E2CA1FF49A0`；替换第一批同路径调试产物。包含前端证据预览，在线使用须部署对应migration007后端及配置API地址。仍未进行本轮实体设备安装/分享验收。

## 第三批用户事实与资格语义

新增shared/profile.schema.json作为11个现有画像字段的类型/范围契约；Rule AST字段从通配pattern收紧为同一字段枚举。Python/TS拒绝未知字段/非法节点，数字字符串、布尔年份、越界排名及错误数组事实保持UNKNOWN，数值不做字符串强制转换。旧非法值不删，profile/meta返回invalid_fields便于修复。

migration008 typed_profile_rule_semantics新增owner的profile_versions与rule_semantics。Profile/Case Fact写入先完整校验，错误无部分保存；记录user_input及revision，不放进进程全局画像。所有scope/eligibility硬条件使用Kleene AND合并，不再只读第一条规则；action_trigger独立，不用于认定资格，缺失字段和失败规则及证据分别返回。GET evaluate只读，写入事实时重新计算。

本地规则抽取改为独立rule_candidates：年级/排名/人数/培养层次等条件绑定命中的局部证据，避免把所有文档行附到每条规则。明确限定2023级而用户2024级可硬否决，年级符合但缺排名保持UNKNOWN。Demo的可选德育材料规则在样例bootstrap显式标action_trigger，样例已有种子升级时只补规则类别，不重置用户状态。

模型Schema新增audience/submission/external_references，非空必须提供真实原文短引；Task标document/suggestion及可选建议耗时。禁止模型把排名/年份等硬资格伪装成action_trigger。Review保留完整最新候选快照、输入hash、Schema及画像revision；这是最新分析快照，完整多版本历史仍待做。模型不输出资格结论，也不因Schema扩展自动接触用户画像。

独立测试：test_profile_facts.py、test_relevance_service.py、test_profile_matching_api.py、test_ai.py；前端profileFacts.test.ts与共享规则向量。node scripts/test-harmony-rules.mjs针对实际ArkTS源码转译后验证11个语义向量及字段一致性，不是SDK原生构建/HAP验收。

本批前端35项通过、vue-tsc通过；后端全量93项通过，后续事项事实写入重算作专项复验。360/390px进一步覆盖建议步骤标记、画像越界不发请求、合法数值提交、未知字段为空及成功反馈。真实LLM、原生鸿蒙编译、实体Android与iOS仍未验收。下一批接真实知识文档入库/检索；兴趣偏好、完整日期时刻、复杂依赖和Privacy Guard仍未完成。

第三批APK更新为10,500,301字节，SHA-256 `B68EBE26666999C715F0723C2D8F4C20073930828EF29DD61FE563B0574B00A7`，仍为同路径调试构建，需部署migration008后端。

## 第四批真实知识资料

migration009 private_knowledge_corpus：真实资料映射到Document，按段落/长度分块并保存line IDs/页码；知识索引和原件按owner隔离。当前为本地TF-IDF词项向量余弦召回与原文摘录，不伪称神经语义Embedding或大模型生成回答。无依据不补答；每条摘录返回真实来源、chunk/line定位，匹配分数不是概率。查询先owner过滤，容量超限明确拒绝。

知识资料库页面支持明确同意后文本/文件入库、查询来源、删除索引。Case规则依据页支持人工核对并关联条款，生成本Case Evidence和候选规则，确认状态失效。关联幂等，删除知识索引后已确认引用保留快照/原件关联，不断开历史依据。

后端全量96项通过，知识专项3项独立通过；前端35项及类型检查通过；360/390px扩展入库同意、查询及来源显示通过。没有外部模型调用或新增依赖。继续下一阶段文件隐私检测及永久脱敏；最终APK统一在后续收口重建。

## 本批验证及产物

全量后端70项通过，前端23项通过，vue-tsc通过；另新增确认取消已有日程的事务回滚测试单独复验。360/390px浏览器确认流程通过，使用Mock API；没有本轮Android实机或真实模型调用验收。

Android调试构建成功，产物 `E:/ZhiShi/deliverables/Zhishi-RuleFlow-debug.apk`，10,010,236字节；SHA-256：`A5AAB4FAC75407CF8E1AA98C59A7CB78D899F84994CAFEF25A4E8BD62A225AAE`。构建时间UTC 2026-10-14T04:08:22Z。APK包含本轮前端变更，后端须部署对应代码；默认服务地址未设为可供实机访问的生产服务，不把构建成功当作在线能力实机完成。

原有工作区变更保留，本轮没有Git提交、推送或发布；Word设计原件未改，工程设计/API文档同步更新。测试使用临时Vault目录，避免触碰真实材料。


## 第五阶段：隐私与脱敏副本

上传入口增加Privacy Guard及明确确认；图片/PDF可扫描行级敏感项和二维码区域，选择后生成永久遮盖副本并保留原件。migration010按owner保存脱敏记录，不存原始敏感匹配值。PDF文字层移除、图片像素遮盖、版本/越权/同意/无坐标失败均有独立测试。后端全量101项、前端38项及类型检查通过；360/390px隐私选择/同意/副本下载通过。二维码检测不解码，未标注姓名地址与漏检仍需人工核对，风险分数非概率。原件包含真实内容，必须按账户保护；尚未做外部模型或实体设备验收。

## 第六阶段：依赖、任务设置与完整草稿

migration011/014/015新增owner排程草稿、任务排程设置、锁定与依赖来源。候选改稳定内容ID，重分析复用同标题旧步骤，未匹配旧步骤标previous供用户保留/取消核对。只有同句明确“先…然后…”等关系形成依赖；绑定短引、缺前置拒绝、环在确认前拒绝，人工边生成用户填写Evidence。历史无来源边标review_needed。

排程在拓扑可执行集合按0.40U+0.30I+0.15D+0.15P排序：U=1/(1+距截止天数/7)、I=用户重要性、D=后继可达比例、P=用户执行偏好。截止及依赖为硬约束；不是最优性或可达性保证。用户明确设置估计耗时、是否拆分、30分钟倍数的片段上下限；默认30分钟是建议估计。预览最多90天/1000任务。可拆任务尝试早且较长片段，整项安排不足则撤销该项所有候选片段，返回required/available minutes；后继以所有片段末尾判断。

偏好包括工作小时、每日任务上限及课程/忙碌/任务间缓冲；周期课程/忙碌最多13次，按时区每周展开，任何冲突整体回滚。所有已有安排在预览中保持，锁定须显式解锁才能编辑/删除。修改有后继的安排不能破坏已安排后继，删除前置安排须先移除后置。拆分任务可逐片编辑，但不能绕过依赖、占用和截止。

POST schedule/drafts保存不可变建议与tasks/edges/items/reviews/planning/locks指纹；commit在BEGIN IMMEDIATE重查，整份落库或整体拒绝。重复提交幂等。POST schedule/preview仍为无持久化预览，移动页改整份确认。独立tests：test_dependency_candidates、test_schedule_drafts、test_schedule_preferences、test_schedule_splits、test_schedule_series_locks。三空隙拆分/不可拆、前置绕过、截止、限额、缓冲、锁定、周期回滚均覆盖。

## 第七阶段：真实执行、来源关系及事实时效

migration012保存不可变分析版本及import→授权Evidence绑定。Real批次同步执行并返回真实终态，不再按未来时间伪装queued；仅明确Demo模式保留时间投影。重试有单独同意、owner过滤、processing执行记录，实际重新分析，不抓取未知新内容；失败仅存ANALYSIS_FAILED，不含原文/模型错误正文。取消在候选写事务前检查，已取消不会落库新候选。服务重启后仍在processing的记录需显式取消后重试，不声称有自动恢复执行器或可靠异步队列。

相同规则用内容ID复用，不自动删除旧/人工规则；不同版本冲突仍交给人工核对，不能宣布新模型输出覆盖官方规则。UI提供分析历史及保存证据的重新分析入口。批次链接保存原件和标准行，附件仅发现，不自动访问；每项单独确认后用同一SSRF/文件校验入口获取，并保存parent_source_id。

PDF原生文字页补嵌入图片区域OCR，单页最多16区域，保留局部坐标及confidence；混合页/旋转页通过FakeOCR验证。复杂重叠版面、图表推理/图片语义理解仍不作完成声明。图片OCR为自部署后端，发送前用户确认，并非端侧OCR。

migration013保留事实填写历史及明确valid_until。到期事实变NULL参与推理，UNKNOWN并提示缺字段，不降FALSE。字段无声明有效期时不自动推断过期；用户须定期核对。migration016软关注分类独立存储，按Case类别匹配并生成用户填写Evidence；relevance_level区分preferred/eligible/needs_verification/not_eligible，不影响eligibility_truth。画像页面可填写排名有效至、查填写历史并保存关注分类。

独立tests：test_analysis_retry、test_link_candidates、test_fact_history、test_interests；原解析/Rule/DAG/share入口回归同时运行。完整UI脚本现在覆盖360/390px确认过期、原图重试、隐私副本、历史重试、附件单项确认、画像与软兴趣、知识入库、耗时拆分设置、草稿过期及整份确认；另检查全部API阻断时Offline Demo。


## 第八阶段：本轮收口与产物

前端38项、vue-tsc通过；360/390px扩展交互与API全部阻断的Offline Demo通过；ArkTS源码11向量通过（不是SDK/HAP构建）。Android调试构建及apksigner签名校验通过，APK确认包含本轮拆分、原子草稿、历史与脱敏页面。

产物：E:/ZhiShi/deliverables/Zhishi-RuleFlow-debug.apk，10,636,284字节，SHA-256 `A061E826DD9A1198462B5326BACD8BC4CB47ABE4880C1C15FBCB02535DA84B40`。替代早期同路径APK，需对应migration006–016后端；默认API部署/服务可达性仍需实际配置。当前adb无连接设备，未发现鸿蒙SDK/Xcode工具，实机/HAP/IPA是环境阻塞，不作完成声明。

代码与工程文档按阶段完成，本轮没有提交、推送、部署或发布。原Word设计文件保留；新增SMART_RECOGNITION_SUBFUNCTIONS.md与升级说明，原件中的目标规格不能当作已实现功能或操作授权。检测、排程与RAG边界见已知限制最新章节。


最终复验：后端全量128项通过；前端38项与类型检查通过；360/390px及全部API阻断的Offline Demo通过；ArkTS源码11共享向量通过。最后增加手工截止严格校验/用户Evidence、重新确认保留耗时依据、新依赖不得破坏已安排日程及回滚验证。最终git diff --check通过。APK为10,636,284字节，SHA-256 A061E826DD9A1198462B5326BACD8BC4CB47ABE4880C1C15FBCB02535DA84B40；签名与本轮页面打包检查通过。

所有本轮工作包的可本地验证代码/测试/工程文档已收口；实机、鸿蒙/iOS工具链及真实外部模型/神经Embedding仍为未验收项，完整生产规格没有冒充完成。升级与验收步骤见BACKEND_UPGRADE_2026-10-14.md。
