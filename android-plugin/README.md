# Android 分享入口

将本目录中的 `ShareReceiverActivity.kt` 合并至 Capacitor 生成的 Android 工程 `android/app/src/main/java/com/zhishi/ruleflow/`，并把 `AndroidManifest.xml` 的 activity 声明合并至 app Manifest。它以 `ContentResolver` 复制分享 URI，限制 20MB/10 文件，绝不假设真实路径或自动上传。复制完成的文件及文本应写入 `SharedPreferences` 的 pending import 队列，再由 Capacitor Web 层在启动后读取并跳转导入确认页。
