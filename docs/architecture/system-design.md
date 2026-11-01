# 系统设计摘要

`移动端本地画像与事项缓存 → OfflineDemoRepository（无网可运行） / ApiRepository → FastAPI 导入、规则、任务、证据模块`。

规则使用受 Schema 约束的 JSON AST；解释包含三值结果、缺失字段、失败条件、证据 id 与执行轨迹。任务以有向无环图保存，Demo 在 UI 以按拓扑层级的步骤卡显示。用户可改任务状态，不能改系统证据。

所有结论、材料和任务均链接至 `document_blocks` 风格的 EvidenceRef，显示来源名、页码、定位及短引文。隐私遮盖发生于客户端导入确认前；默认离线模式不发送内容。
