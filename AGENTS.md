# 知事 RuleFlow 工程约束

1. 先保持 Offline Demo 可运行；任何在线/LLM 功能失败不得影响 Demo。
2. 禁止把 API Key、keystore、真实个人资料、真实上传文件或 .env 提交到 Git。
3. 所有用户可见结论、任务、材料、deadline 必须附有效 EvidenceRef；没有证据就显示“待核对”，不得编造。
4. Rule AST 只能使用 shared/rule_ast.schema.json 定义的操作符和画像字段；禁止 eval、动态执行代码、SQL 拼接或模型输出直接执行。
5. 三值逻辑 UNKNOWN 不能降级为 FALSE；缺字段必须明确提示用户补充什么。
6. 每次修改 Rule Engine、DAG、解析器或分享入口时，必须运行相关单测；修改 UI 状态时补充移动端测试。
7. Android 分享的 content URI 必须通过 ContentResolver 读取，不能假设真实文件路径；不可静默上传。
8. 上传前必须走 Privacy Guard，并由用户明确确认；日志和错误上报不得含原始敏感内容。
9. 新增依赖须说明必要性，优先官方/成熟库，避免未维护原生插件；不得为便利关闭 TLS/SSRF/文件校验。
10. 改动前检查工作区现有修改；不要覆盖无关文件。完成后汇报改动、测试、已知限制与 APK 产物路径。

## 完整版 v2 追加约束

1. 生产逻辑必须使用通用 Case、Fact、Rule、Evidence、Task 模型；综测只作为明确标记的回归样例。
2. 样例、本机和账户数据分区隔离。每一个私有资源必须按 owner_id 授权；禁止进程级画像或任务状态。
3. 账号使用安全密码哈希、短 access token 与可轮换、可撤销的 refresh 会话；不得把长期凭据放进 Web localStorage。
4. 新输入的分析失败或服务未配置必须如实呈现，禁止返回预置 Demo 冒充结果。
5. 原生鸿蒙须为 ArkTS/ArkUI 工程；PWA 不可作为鸿蒙原生完成凭据。没有 SDK、设备或签名时记录 blocker，继续完成可验证的共享工作。
