# 知事 RuleFlow

面向 Android、iOS 与 HarmonyOS NEXT 的复杂通知理解和个性化执行应用。系统把网页、PDF、Word、Excel、截图与文本转成可追溯的规则、材料和任务 DAG；缺少个人事实时严格返回 `UNKNOWN`，不会把未知当作不符合。

## 已落地能力

- 账号注册、邮箱验证流程、登录、访问/刷新令牌轮换、密码重置与设备会话。
- SQLite 持久化和 `owner_id` 隔离；Demo、本机示例和账户数据不混用。
- URL 安全抓取（协议、DNS/IP、逐跳重定向和体积限制）、TXT/HTML/PDF/DOCX/XLS/XLSX/PNG/JPEG 解析；扫描 PDF 与图片使用本地 OCR。
- 保守的通用规则抽取、Kleene 三值 Rule AST、EvidenceRef、材料清单、Task DAG、TXT/ICS 导出和增量同步 API。
- 可选的服务端 LLMProvider：支持 DeepSeek 等 OpenAI 兼容模型，模型输出必须经过结构化格式、AST、EvidenceRef 和原文短引校验；未配置或失败时明确回退本地分析。
- Android 系统分享入口、私有目录复制、待确认队列和 Capacitor 原生桥；已构建可安装调试 APK。
- iOS Capacitor 工程与 Share Extension 源码；HarmonyOS NEXT ArkTS/ArkUI 原生工程基线。

## 启动后端

```powershell
cd server
E:\DevTools\PythonPortable\python.exe -m pip install -r requirements.txt
E:\DevTools\PythonPortable\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

生产环境必须设置 `APP_ENV=production`、随机 `REFRESH_TOKEN_PEPPER`、持久化 `DATABASE_PATH`，并在反向代理后启用 HTTPS。生产邮箱验证需接入 SMTP；开发环境会返回一次性验证 token 便于验收。

## 移动端与 Android 打包

```powershell
cd mobile
npm install
npm run dev
cd ..
.\scripts\build-android.ps1
```

脚本把 Android SDK、Gradle 与缓存固定在 E 盘工具目录，输出到 `deliverables/Zhishi-RuleFlow-debug.apk`。APK 为了避免仓库膨胀不提交至 GitHub，详见 `deliverables/README.md`。正式发布必须用未提交到仓库的独立密钥构建 release AAB/APK。

## 验证

```powershell
cd server
E:\DevTools\PythonPortable\python.exe -m pytest -q -p no:cacheprovider
cd ..\mobile
npm test
npm exec vue-tsc -- --noEmit
```

iOS 的 IPA 必须在 macOS + Xcode + Apple 签名环境产生；HarmonyOS HAP/App Pack 必须在 DevEco Studio + 对应 SDK/签名环境产生。Windows 上不伪造这两类签名产物。
