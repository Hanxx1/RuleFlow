# 知事 RuleFlow HarmonyOS 原生客户端

这是 ArkTS/ArkUI 原生工程的共享业务起点，不是 PWA 容器。`entry/src/main/ets` 包含原生 `UIAbility` 与 ArkUI 页面，规则引擎按 `shared/test-vectors/rule-engine.json` 的 Kleene 三值语义实现。

未在本机生成 HAP：当前未检测到 DevEco Studio、HarmonyOS SDK、签名或目标设备。取得工具链后，从本目录在 DevEco 打开工程，配置 bundle 名和签名，再运行同一测试向量及分享/Want 验收。
