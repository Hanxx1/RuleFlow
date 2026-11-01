# 知事 RuleFlow 交付物

- `Zhishi-RuleFlow-debug.apk`：Android 调试安装包，仅用于验收与演示；该二进制构建产物不提交至 GitHub。
  - SHA-256：`3164C262C806DD27DDCC909971AE64658EC88D32AB3BD042F434BD19F123638E`
  - 包名：`com.zhishi.ruleflow`；版本：`1.0`；minSdk 22；targetSdk 34。
- `Zhishi-RuleFlow-win-x64.exe`：Windows x64 单文件离线演示程序，使用微软官方 WebView2 承载与移动端相同的前端构建；二进制产物不提交至 GitHub。
  - SHA-256：`6346C08F7AC9457126F97A4FC3722B884FC90CC893611C65069302FCF58A5C42`
  - 自包含 .NET 运行时；目标电脑仍需具备 Microsoft Edge WebView2 Runtime。当前为未代码签名的验收构建。
- 正式上架包必须在受控环境中使用独立签名密钥构建，不得提交调试密钥或真实服务密钥。
- iOS 工程位于 `mobile/ios`，必须在 macOS + Xcode 上配置团队签名后产出 IPA。
- HarmonyOS NEXT 工程位于 `harmony`，必须在 DevEco Studio 中配置签名后产出 HAP/App Pack。


2026-10-14 最新调试APK：`Zhishi-RuleFlow-debug.apk`，10,636,284字节，SHA-256 `A061E826DD9A1198462B5326BACD8BC4CB47ABE4880C1C15FBCB02535DA84B40`。包含候选确认、文件证据/脱敏、真实资料库、画像时效/软偏好、任务分段/锁定/周期课程和整份草稿。需migration006–016后端；签名校验通过，未进行本轮实机验收。


## 2026-10-14 公开实例评测与阶段补充

已完成200份不同公开实例的真实DeepSeek评测及失败回归，197份通过结构/证据校验，3份短引不一致拒绝；不代表98.5%语义准确率，不属于模型训练。新增12份离线公开实例、17项有证据的行动；逐任务截止日期、6个画像字段及9类生成附件回归已落地。真实LLM移动浏览器链路通过，安卓真机仍缺设备。详见 [阶段报告](../docs/PUBLIC_CORPUS_200_VALIDATION_2026-10-14.md)。最新APK：`E:/ZhiShi/deliverables/Zhishi-RuleFlow-usb-debug.apk`，SHA256 `4460FE10E2834994518A4AE260360A6A84DF6796BB29C1AD431DA0D93D4DA9C8`。


## 2026-10-14 客户端资料五阶段补充

客户端画像、补充候选、可见资料卡、版本/备份/清理、本机匹配、单双周课表与确认后的占用时段排程、缺附件提醒和重新分析已接入。新一轮200多格式实例首轮174校验通过，失败回归后192通过、8拒绝；110个附件引用场景，40组课表回放无课程冲突。数据为受控格式转换，独立人工全文准确率未验收。后端151、前端58项测试及移动端流程通过；安卓真机暂缓。详见 [五阶段报告](../docs/CLIENT_WORKSPACE_FIVE_STAGES_2026-10-14.md)。当前APK SHA256：`7D4978905E9F0269A99C5930275684B32D3FCD6F4534219AE1626DCB1C1F598C`。
