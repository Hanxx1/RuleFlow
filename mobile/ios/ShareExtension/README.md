# Xcode target

在 macOS 上为现有 `App.xcodeproj` 添加 Share Extension target，产品标识使用
`com.zhishi.ruleflow.ShareExtension`，将本目录的 Swift、Info.plist 与 entitlements 加入该 target，
并为主 App 与扩展同时启用 App Group `group.com.zhishi.ruleflow`。扩展只写入待确认队列，不上传内容。
