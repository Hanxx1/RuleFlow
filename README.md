# 知事 RuleFlow

现有通知理解、证据追溯、资料与任务计划软件的保守工程整理版本。采用 Vue 3 / TypeScript / Pinia / Capacitor、FastAPI 和 SQLite。不是重新开发的产品；来源见 [docs/development/PROVENANCE.md](docs/development/PROVENANCE.md)。

## 当前边界

Web 与后端核心测试、Web 构建有本次验证记录。Android 原生分享源码保留，Capacitor sync 已验证；本机缺少 SDK，未生成或验收 APK。iOS 分享扩展与鸿蒙仍是待完成/待设备验收的工程基线。真实在线 LLM、Docker、Windows 发布包不在本次已通过范围。

## 干净安装（Windows PowerShell，从仓库根开始）

已验证 Python 3.11.9、Node 24.18.0。保留 npm lockfile；不需要任何固定盘符。安装路径含中文、空格也可使用。

```powershell
python -m venv server/.venv
& server/.venv/Scripts/python.exe -m pip install -r server/requirements.txt -c server/requirements.lock
npm.cmd --prefix mobile ci
```

requirements.lock 是已验证 Windows/Python 3.11 的依赖约束；其他操作系统/Python 版本应单独验证，不能直接宣称通过。Linux/macOS 可使用 venv 的 bin/python 和 npm；Android、iOS、鸿蒙各自需要对应工具链。

## Web 与离线样例

```powershell
npm.cmd --prefix mobile run dev -- --host 127.0.0.1
```

打开终端显示的 URL。离线样例不需要账户/后端；浏览器 PWA 完整离线缓存仍有历史限制，不等同 APK 内嵌资源离线能力。

## 本地后端（另开终端，从根目录）

```powershell
& server/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir server --host 127.0.0.1 --port 8000
```

开发模式默认使用新工程自己的 server/data；不复制旧数据库或上传资料。`.env.example` 仅说明变量，**Python 不会自动加载它**；可以在当前终端设置 `$env:变量名`，或显式使用 Uvicorn 的 `--env-file`。根模板中的密钥示例必须替换，不能作为生产凭据使用。

前端默认连接 127.0.0.1:8000。需要改地址时，在 mobile/.env.local 设置 `VITE_API_BASE`，重新启动开发服务/重新构建。真机中的 127.0.0.1 是手机本身，需配置可访问的后端地址或明确使用 adb reverse。VITE_ 配置会打包进入客户端，严禁填写秘密。

## 检查和生产 Web 预览

```powershell
& server/.venv/Scripts/python.exe -m pytest server/tests -q -p no:cacheprovider
& server/.venv/Scripts/python.exe scripts/check-api-contract.py
& server/.venv/Scripts/python.exe scripts/smoke-startup.py
python scripts/check-paths.py
python scripts/check-docs.py
node scripts/check-demo.mjs
npm.cmd --prefix mobile test
npm.cmd --prefix mobile run build
npm.cmd --prefix mobile run preview -- --host 127.0.0.1
node scripts/test-harmony-rules.mjs
```

后端测试每例使用独立数据库和临时文件根，不依赖真实账户或 LLM。check-api-contract 对比重构前完整 OpenAPI 指纹；有意变更接口时必须经评审更新基线，不能为消除失败自动重写指纹。check-demo 校验 shared 与 public 的 8 份样例副本一致，不改变现有 URL。

## Android

安装与现有 Gradle 8.2.1 / AGP 8.2.1 兼容的 JDK 和 Android SDK；配置 JAVA_HOME、ANDROID_HOME/ANDROID_SDK_ROOT，或 mobile/android/local.properties 的 sdk.dir。Gradle 使用项目 Wrapper，不需要全局 Gradle。不要提交 local.properties、签名密钥和 SDK。

```powershell
./scripts/build-android.ps1
# 如需编译 instrumentation 测试包：
./scripts/build-android.ps1 -WithTests
```

脚本执行 Web 构建、Capacitor sync、Wrapper 构建，任何一步失败都不会继续复制旧 APK。输出为 deliverables/Zhishi-RuleFlow-debug.apk（忽略）。SDK 未配置会明确停止，不自动安装 SDK。原生插件名、applicationId 和分享协议未改变。编译通过也不能代替真机分享验收。

## 目录与扩展边界

- mobile/src/features：imports、cases、planning 核心流程，以及 account 的账户敏感请求。
- mobile/src/core：HTTP 与原生分享；demo：样例加载/计划。其余页面、通用组件、服务保留原结构。
- server/app/main.py：装配及尚未拆分的业务；api/planning.py：排程路由；schemas.py：请求模型；bootstrap.py：原有建表入口。
- server/app/services、providers：现有业务与适配实现；SQLite 连接生命周期保持原样。
- shared：规则/画像 schema、跨端向量与去标识样例。
- scripts：从自身位置定位工程的构建/验收工具。可选语料脚本使用 ZHISHI_TEST_FONT 指定中文字体。
- docs：按 architecture / development / product / testing / archive 分类，统一入口见 [文档导航](docs/README.md)。历史资料不代表本轮已验收状态。
- desktop、harmony、mobile/ios：原平台工程。android-plugin 是未接入的旧模板，实际 Android 实现在 mobile/android。

[协作规则](docs/development/CONTRIBUTING.md) · [原始基线](docs/testing/BASELINE.md) · [整理验收报告](docs/testing/REFACTOR_REPORT.md)

完整文档索引：[docs/README.md](docs/README.md)。
