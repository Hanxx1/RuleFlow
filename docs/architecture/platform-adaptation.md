# 三端适配

## Android

Capacitor 是正式容器。`ShareReceiverActivity` 支持文字、URL、图片、PDF、DOCX、XLSX 和多文件分享；通过 `ContentResolver` 读取后复制到 App 私有目录，限制 10 个文件/单文件 20 MB。`PendingImportsPlugin` 把待确认队列交给 Vue，用户查看隐私预览并明确同意后才请求分析。`scripts/build-android.ps1` 可复现 APK 构建。

## iOS / iPadOS

主工程位于 `mobile/ios/App`，Share Extension 源码位于 `mobile/ios/ShareExtension`。扩展用 App Group `group.com.zhishi.ruleflow` 写入待确认队列并限制文件大小。需要在 Xcode 中创建/关联扩展 target、为主 App 和扩展启用同一 App Group，并配置 Apple Team 后 Archive。Windows 不能合法生成已签名 IPA。

## HarmonyOS NEXT

`harmony/` 是 ArkTS/ArkUI 原生工程，不是 PWA 替代物；包括 Stage 模型 UIAbility、原生页面、独立三值规则引擎、模块与 hvigor 配置，并声明 `ohos.want.action.sendData` 分享入口。需在 DevEco Studio 安装与 `compatibleSdkVersion` 匹配的 SDK、配置签名后构建 HAP/App Pack，并在真机补做 Want、文件沙箱与通知测试。
