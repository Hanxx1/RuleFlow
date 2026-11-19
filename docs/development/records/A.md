# A 开发工作记录

本文件累积 A 的实际工作证据，不替代正式比赛报告或原始交互记录。

最新状态（2026-11-08）：RF-006 进行中；APK 构建证据已归档，A 已口述初步真机验证结果；设备与业务证据待补，新增登录状态保持问题待独立修复评审。暂不建议整卡进入待验收，不标记完成。以下按日期保留历史状态。

## 2026-11-05 · RF-006 Android 当前版本基线

### 1. 基本信息

- 项目：有绪 CampusWeave；旧工程名知事 RuleFlow 保留，本次不开展全局品牌迁移。
- 负责人：A。目标：取得当前源码第一次 Debug APK 构建证据，交付文件名为 `CampusWeave-debug.apk`。
- 状态：**受阻**。Web 构建及 Capacitor sync 通过，Gradle Wrapper 启动失败，未产出 APK；RF-006 整卡未完成。
- 分支：`chore/RF-006-android-baseline`。
- 源码基准 commit：`ac9e07ce6574d4ac8303319d65cb80f00f221c6a`；本次脚本和记录为未提交工作区差异，无 commit、push 或 PR。
- 依据：`AGENTS.md`、`README.md`、`docs/development/CONTRIBUTING.md`、团队执行计划第 10 节和首批任务 RF-006 卡。

### 2. 实际完成与未完成

- 构建前在真实仓库根目录确认 main / 上述 HEAD，工作区干净，无未跟踪文件；目标任务分支不存在，随后从该 HEAD 创建并切换。
- 历史评估基线 `c589990` 存在。与当前 HEAD 比较，仅新增 5 份文档：工作量评估、团队执行计划、首批任务、初赛计划书草稿、视频方案；源码和配置无变化。
- 前期只读检查发现 PATH Java 8、JAVA_HOME 指向 JDK 21，而另有可运行的 JDK 17；当时常见位置未发现 Android Studio/JBR 或 SDK。本次没有安装或配置 Android Studio，不宣称其已安装。
- 用户随后报告安装 SDK；本次实际核实 D 盘 SDK 组件存在。此次没有执行安装、升级或全局环境变更。
- 构建前 deliverables 下无 APK，Git 不跟踪 APK；新旧交付 APK 和默认中间 APK 均不存在，无旧 APK 被覆盖。
- 仅将脚本 Debug 交付文件名改为 `CampusWeave-debug.apk`，检查 diff 后执行一次构建；失败后没有重试、权限修改或源码修复。
- 尚未完成：Gradle 构建、APK 交付及真机安装/连接/分享验收。RF-001 独立维护，本记录不将其标为完成。

### 3. 技术说明

- Windows 10.0.26300.0；Node 24.18.0、npm 11.16.0；构建进程内 java/javac 实测均为 17.0.16。
- JDK：`C:\Program Files\Java\jdk-17`；SDK：`D:\Android\Sdk`。
- SDK Platform API 34 / Android 14 / Revision 3；Build-Tools 34.0.0；Platform-Tools 37.0.1；Command-line Tools 元数据 23.0。
- 项目 Wrapper 指定 Gradle 8.2.1，AGP 配置 8.2.1，compileSdk/targetSdk 34、minSdk 22，Java 编译级别 17。此次 Wrapper 未成功启动 Gradle，不能记录为 Gradle 运行验证通过。
- `scripts/build-android.ps1` → `npm.cmd run android:sync` → `vue-tsc --noEmit` → Vite → Capacitor sync → `gradlew.bat assembleDebug --no-daemon` → 复制交付 APK。
- 仅修改脚本复制目标文件名；默认输入仍为 `mobile/android/app/build/outputs/apk/debug/app-debug.apk`。未修改 applicationId、包名、Manifest、显示名称、资源源码、业务代码或 AndroidTest APK 名称。
- README 仍记载旧交付名，此次按授权范围未同步修改；当前交付名以脚本和本记录为准。

### 4. 问题与处理

- Java 来源冲突：仅在本次 PowerShell 构建进程设置 JAVA_HOME/PATH，使 java/javac 指向 JDK 17；不改用户或系统配置。
- 之前 SDK 缺失：本次已确认组件安装存在，并在构建进程设置两个 SDK 路径变量；未创建 local.properties。
- 本次阻塞：Wrapper 打开 `<USERPROFILE>\.gradle\wrapper\dists\gradle-8.2.1-all\d8pvvlun5bx6sdtwqhf8y9z4b\gradle-8.2.1-all.zip.lck` 时抛出 `java.io.FileNotFoundException`，原输出含“拒绝访问”；随后脚本抛出 `Android build failed (exit 1).`。
- 定位：失败发生在 Wrapper 缓存锁访问阶段，尚未进入 assembleDebug 任务，不是已证实的 Android 源码编译错误。执行环境对工作区外写入有限制，可能相关；未进一步验证操作系统 ACL 或文件占用，不能断言唯一原因。
- 处理结果：保留现场并停止。未删除锁文件、未重置缓存、未提权重试、未修改 Gradle/AGP/依赖版本。Vite 的 CJS Node API 弃用警告未阻止 Web 构建。

### 5. 测试与验证

在仓库根目录实际执行（环境设置仅限该 PowerShell 进程及子进程）：

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-17'
$env:ANDROID_HOME = 'D:\Android\Sdk'
$env:ANDROID_SDK_ROOT = 'D:\Android\Sdk'
$env:PATH = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:PATH"
java -version
javac -version
& .\scripts\build-android.ps1
```

| 项目 | 预期 | 实际 |
|---|---|---|
| Vue TypeScript | 无类型错误 | 通过；后续 Vite 已执行 |
| Vite Web 构建 | 生成 web-dist | 通过；178 modules transformed，built in 17.48s（仅该阶段工具输出，不是总耗时） |
| Capacitor sync | 复制资源并更新插件 | 通过；preferences 6.0.4，Sync finished |
| Gradle assembleDebug | 生成新 app-debug.apk | 未通过；Wrapper 访问锁文件失败，任务未执行 |
| 最终交付 | CampusWeave-debug.apk | 未生成；大小和 SHA-256 不适用 |
| 单测、instrumentation、真机安装/登录/网络/分享 | 后续验收 | 未测试 |

### 6. 过程证据与差异

- 原始命令及输出保留在本次 RF-006 Codex 会话中。未另存截图或录屏。
- 本地 PowerShell transcript：`.runtime/rf006/build-20261105-122654.log`（Git 忽略，不纳入提交）。该 transcript 未完整收录 native 工具输出，只能作为补充，不能作为完整构建日志；下列摘录来自实际工具输出并去除个人路径。

```text
vite v5.4.21 building for production...
✓ 178 modules transformed.
✓ built in 17.48s
[info] Found 1 Capacitor plugin for android:
       @capacitor/preferences@6.0.4
[info] Sync finished in 4.714s
Exception in thread "main" java.io.FileNotFoundException: <USERPROFILE>\.gradle\wrapper\dists\gradle-8.2.1-all\d8pvvlun5bx6sdtwqhf8y9z4b\gradle-8.2.1-all.zip.lck
Android build failed (exit 1).
```

- 失败后确认 `deliverables/CampusWeave-debug.apk`、旧名交付 APK、默认 app-debug.apk 均不存在。
- 预期 Git 差异：`scripts/build-android.ps1` 一行文件名修改，以及本记录新文件。Capacitor 的受跟踪配置无内容差异，无意外受跟踪源码变化；`git diff --check` 通过。
- 正常生成/更新内容：`mobile/web-dist`、Android assets、生成 config.xml 和 Cordova 插件目录；日志位于 `.runtime/rf006`，均受忽略规则覆盖。Android `.gradle` 已存在，未将其误记为本次新增。未清理任何产物或缓存。
- 性能、流量、模型 usage：未测量；无虚构耗时或 token 统计。

### 7. 评审与后续

- 待 A 核对记录；脚本局部修改由 B 或相关模块负责人交叉评审，尚未评审/验收。
- 下一步由 A 确认处理 Wrapper 缓存写入权限的方式，例如在获授权的执行环境复用现有缓存，或为构建进程指定可写的 GRADLE_USER_HOME；本次未实施。需考虑首次缓存填充的固定版本下载。
- 构建解除阻塞后记录真实 APK 大小/hash，再安排真机安装、后端可达地址/健康检查/登录、已有页面及冷/热分享文本、URL、图片/文件、多文件、连续分享。
- 由 C 核对分享业务，B/D 协助入口与网络；验证未确认不上传、取消恢复、成功仅清理对应快照、失败保留原因。设备/系统、样本、录屏和实际后端往返证据尚缺。
- 当前准确结论：完成一次构建尝试，Web 与同步成功，Android 构建受环境访问阻塞；不能宣称 APK 或 RF-006 已完成。

## 2026-11-06 · RF-006 构建恢复与 APK 核验

### 1. 基本信息与证据来源

- 负责人 A；分支 `chore/RF-006-android-baseline`；HEAD 实测仍为 `ac9e07ce6574d4ac8303319d65cb80f00f221c6a`。
- 状态：进行中；构建阻塞已解除，阶段性修改待评审，RF-006 整卡未完成。RF-001 状态不在本次更新范围。
- 普通 PowerShell 的执行过程和成功输出由 A 在本次会话提供；本次 Codex 未重新构建，仅实测 APK 存在性、大小、SHA-256 和 Git 差异并追加本记录。未提供完整成功日志文件位置，不虚构日志或截图。

### 2. 失败过程与恢复

1. 第一次 Codex 构建：访问 C 盘 Gradle 缓存锁文件被拒绝，assembleDebug 尚未执行。随后只读诊断确认锁文件存在且可读、CodexSandboxUsers ACL 条目仅有读取/执行权限，执行进程处于低完整性级别，缓存不在允许写入的工作区内；这些证据支持沙箱访问限制这一诊断。诊断时未发现相关 Java/Gradle/Studio 进程，但不能据此断言失败当时没有占用。
2. A 补充报告：第二次尝试 D 盘独立缓存时，Gradle 下载约 50% 后报 `java.net.SocketException: Connection reset`。本次未复现或测量下载比例，未删除/迁移该缓存。
3. A 补充报告：后续验证 C 盘已缓存的 Gradle 8.2.1 可使用 JDK 17 正常启动；随后在普通 Windows PowerShell 复用 C 盘缓存，完成构建。未通过修改源码、升级依赖或删除锁文件解决问题。

### 3. 成功构建环境与命令

- A 报告：Windows；JDK 17.0.16；SDK `D:\Android\Sdk`；Gradle 8.2.1；GRADLE_USER_HOME 为用户 C 盘目录 `<USERPROFILE>\.gradle`（记录去除个人用户名）。
- 项目既有 AGP 8.2.1、compileSdk 34、Build-Tools 34.0.0；此前已核实 SDK Platform 34。此次没有安装或升级依赖。
- A 实际在仓库根目录执行的命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-android.ps1"
```

- Web 构建、Capacitor sync 均通过（A 提供结果）；Gradle 输出如下。6m 39s 仅为该 Gradle 输出中的时长，不作为整个任务或全部尝试的总耗时。

```text
BUILD SUCCESSFUL in 6m 39s
108 actionable tasks: 108 executed
```

### 4. APK 实测证据

仓库根目录为 `<PROJECT_ROOT>`。以下两个文件均由本次只读检查确认存在：

| 文件（相对仓库根目录） | 字节数 | SHA-256 |
|---|---:|---|
| `mobile/android/app/build/outputs/apk/debug/app-debug.apk` | 9622439 | `7B1E747E1DC85F2ED5BC7D8EF48F8E19BCEF760E270FDBD58AA5410ED4473C75` |
| `deliverables/CampusWeave-debug.apk` | 9622439 | `7B1E747E1DC85F2ED5BC7D8EF48F8E19BCEF760E270FDBD58AA5410ED4473C75` |

- 使用 `Get-Item` 和 `Get-FileHash -Algorithm SHA256` 实测；哈希一致，确认交付 APK 与当前原始构建输出字节一致。结合 A 的执行记录作为此次构建证据，未将哈希比对扩大为运行功能验收。
- APK 来源版本标记为上述 HEAD 加未提交的交付文件名补丁；不能描述成已提交的新源码版本。

### 5. Git 差异和警告

- `git status`、`git diff`、未跟踪文件清单确认：仅 `scripts/build-android.ps1` 一行交付文件名变更，以及新增的 `docs/development/records/A.md`；没有意外受跟踪源码/配置内容变化。
- `git diff --check` 退出码为 0。两个 APK 均被 Git 忽略，未暂存 APK、SDK、缓存、中间产物或私人环境数据。
- Git 曾提示两个 Capacitor 生成 Gradle 配置的 LF/CRLF 转换；没有内容差异，本次未修改换行配置。
- A 报告构建有 flatDir、SDK XML 版本及 Java 过时 API 警告，但构建成功。当前没有证据表明这些警告阻塞本次 APK 交付；因未取得完整警告上下文，不认定它们无运行风险，也不据此自动升级或修复。

### 6. 未测项目、评审与后续

- 真机安装、登录、后端通信、系统冷/热分享链路、取消恢复及上传确认：未测试。单测、instrumentation 测试、设备兼容性及性能/流量：本次未测试；无 AI token usage 统计。
- 已具备提交阶段性 commit 的产物证据和最小改动范围；提交范围应仅为脚本与本工作记录，待 A 审核，B 或相关模块负责人交叉评审仍未完成。本次未 commit、push 或创建 PR。
- 下一步确认测试设备和可达后端地址，使用该哈希对应 APK 安装，记录登录/网络/冷热分享等场景及失败证据。APK 构建成功不等于 RF-006 完成。

## 2026-11-08 · RF-006 人工真机结果补录与登录问题登记

### 1. 基本信息与证据边界

- 负责人及操作结果提供者：A。本节日期为补录日期，各场景实际操作时间和次数未提供。
- 当前分支 `chore/RF-006-android-baseline`，阶段性 commit `1d7a2cd5b8094be11e5717a1b0d98958295ba42f`；此前 APK 构建失败、下载中断、成功及哈希记录保留不变。
- A 报告使用 `CampusWeave-debug.apk` 在真实 Android 手机上测试，电脑本地 FastAPI 后端通过 USB + adb reverse 与手机连接。APK 文件证据引用上节；本轮未从设备读取安装包哈希，也未独立核对运行后端的 commit、数据库路径或完整启动参数。
- 本节真机结果来自 A 的人工操作口述，不是 Codex 本轮重新运行的测试。未提供设备型号、Android/WebView 版本、截图、录屏、详细请求日志或样本清单；不声称这些证据已存在。不记录账户、凭据、性能、流量或 AI token usage。

### 2. 实际验证结果

| 场景 | A 提供的实际结果 | 本次记录结论与边界 |
|---|---|---|
| 安装与启动 | Debug APK 成功安装并启动 | 按人工口述记为该设备上的安装/启动通过；不是多设备兼容验收 |
| 电脑后端健康 | FastAPI 启动成功，GET /health 返回 HTTP 200 | 按口述记为健康检查通过；未取得原始响应或日志 |
| USB 后端连通 | adb reverse 后 App 显示已成功连接后端 | 按口述记为该连接方式下连通通过；不外推 Wi-Fi 或其他网络 |
| 登录与基本功能 | 账号登录、基本功能可以使用 | 初步体验通过；具体功能清单、请求响应和数据核对未提供，不代表完整业务回归 |
| 网页链接分享 | 从其他 App 分享，接收正常 | 初步接收通过；不能推断网页抓取、分析、Evidence 或 Case 数据一致性通过 |
| 图片分享 | 从相册分享，接收正常 | 初步接收通过；不代表所有图片格式、OCR 或上传解析通过 |
| 文件分享 | 文件管理器分享 PDF、DOCX 等测试文件，接收正常 | 仅确认口述中的 PDF、DOCX 接收；“等”不作为其他格式已验收的依据 |
| 取消当前导入 | 用户观察未发现异常 | 初步观察通过；未核对服务器是否新增记录、原生队列/文件是否按指定 ID 清理 |
| 冷启动、热启动、连续分享 | 均实际测试，用户反馈正常 | 初步场景观察通过；启动方式、连续分享次数、顺序及队列 ID 未提供 |
| 后端停止及恢复 | 停止后端尝试导入，恢复后端后重试，用户反馈正常 | 初步恢复观察通过；不等于测试了所有断网情况或已证明重试幂等、无重复数据 |
| 登录状态保持 | 后端持续运行，关闭并重开 App 后经常需要重新登录 | 已发现体验问题，未通过；详见独立问题条目 |

### 3. 对照验收卡仍需补充的检查

- A 补设备型号、Android/WebView 版本、实际 APK/后端版本对应关系、测试日期、连接方式和合成样本标识；按场景保存脱敏截图/录屏及必要请求状态。现有构建日志不能替代真机证据。
- 纯文本分享、单次多文件 SEND_MULTIPLE 未单独确认，记为待核实，不能用连续分享代替多文件测试；未列明的格式、MIME、权限拒绝和大小边界不判通过。
- “未确认不上传”、成功后仅清理本次快照 ID、失败保留具体原因和原始待处理内容，尚缺少针对性观察及日志，待验证。取消未见异常不能代替这些安全与恢复要求。
- C 协助核对分享后的来源/附件、实际保存与解析结果、Evidence/Review/Case 关系、账户归属，以及恢复后重试有无重复或部分写入；服务端持久化与业务数据一致性尚未确认。
- B/D 按原分工协助相关页面及网络；不把初步登录/接收观察扩大为所有模块已回归。上述补测、单测和 instrumentation 本轮未执行。

### 4. 独立问题：Android App 重新启动后无法可靠保持登录状态

**用户现象：**后端持续运行时，关闭并重新打开 App 后经常需要重新登录。发生次数、后台停留时间、退出方式与设备日志尚未提供；不写成每次必现。

**已确认源码缺口（依据上一轮只读检查）：**

- `mobile/src/core/http.ts` 的 access/refresh token 仅在 JavaScript 模块变量中；`setSession` 只赋值，未发现安全持久化 refresh token 的机制。
- `mobile/src/stores/account.ts` 的 Pinia user 初始为 null；`mobile/src/main.ts` / `App.vue` 未发现启动时恢复认证会话的流程。
- 现有刷新由受保护请求返回 401 且内存 refresh 非空触发；进程或 WebView 重建后，内存令牌消失，无法依靠此流程恢复。
- `server/app/auth.py` 的 refresh token 默认有效期为 30 天，access token 为 15 分钟；服务端会话仍有效并不意味着客户端还持有凭据。
- 上轮对照本地 origin/main `ce597a1015bc58bc500abc01b65b777b4070d03c`，认证核心没有已有修复；本轮未联网或同步 main。

**尚未确认：**每次现象是否伴随进程结束或 WebView 重建；划掉任务与后台返回是否相同；是否发生刷新请求、网络失败或服务端拒绝。缺少设备生命周期和脱敏网络证据，不能把客户端缺口认定为所有发生实例的唯一原因，也不能认定是后端故障。

**建议归属与修复边界：**由 A/B 公共技术负责人协调独立修复任务及实施者，A 负责复现和真机回归，B 参与账户隔离/退出清理评审，非实施者交叉审查。单独评审安全凭据存储、启动恢复、刷新令牌轮换与持久化、网络失败重试、主动登出及并发恢复行为；不得将长期凭据直接写入 Web localStorage，不能把普通 Preferences 等同于安全凭据存储。优先限定认证与必要的原生存储接入，不借此修改其他业务、品牌或数据库结构；如需后端协议变化，另行说明兼容性与验证范围。

本问题未修复。本轮只登记，不把后续修复混入此前 APK 构建成果，不安装插件、不重建 APK。

### 5. 状态建议与下一步

- 建议 RF-006 整卡暂保持“进行中”，本次人工验证记录交 A 审核；暂不进入整卡“待验收”，更不标“已完成”。安装/连接和分享入口已有实际进展，但原卡要求的设备证据、多文件、授权与快照清理、失败原因及分享后业务核对仍未齐全；登录状态保持是额外发现、需跟踪的体验缺陷。
- 登录保持问题不否定已报告的安装、连通和初步接收结果，也不替代原卡剩余检查。后续独立修复或明确验收处置后，再结合 C 的数据核对与设备证据评估状态。
- 最小后续：A 补环境/场景证据并区分后台、划掉任务、进程终止的复现；C 核对导入数据与重试一致性；A/B 确认认证修复边界和回归用例。日志仅记录请求路径、状态码、生命周期及凭据是否存在，不保存完整 token、密码或 Cookie。
- 本轮仅更新本记录；未操作手机/后端、未修改真实账号或数据库、未执行构建或测试、未 commit/push/创建 PR。RF-001 和其他任务状态不作调整。

## 2026-11-10 · A 统一集成基线与自动回归

- 范围：A 的构建与集成验收。基线 main `d1d8647beb6710b4e51877b18354399da3077d7c`，工作分支 `chore/a-integration-baseline-20261110`。未修改 B/C/D 业务代码或安排其他成员工作。
- 原 A.md 与 stash 逐字节一致后保留，本节仅追加；原 Android 分支、独有提交和 stash 未动。当前记录尚未提交。
- 将 scripts/build-android.ps1 的交付名称统一为 CampusWeave-debug.apk，README 同步；包名、插件协议、依赖锁文件未变。
- 主线包含通知附件填表、来源移交基线测试和 RF-043 修复；合并不等于完整业务闭环或团队签认。日历网格仍按演示能力管理。
- 环境恢复：离线 npm ci 缺缓存失败，联网恢复后发现开发工具缺失，显式 npm ci --include=dev 成功。未升级依赖；npm 审计报告 16 项（9 moderate、4 high、3 critical），未做 audit fix，实际影响待审查。
- 后端：server/.venv/Scripts/python.exe -X utf8 -m pytest server/tests -q -p no:cacheprovider --tb=short --disable-warnings，223 passed、5 warnings。隔离数据库及合成资料，无真实模型调用；最初受限环境挂起进程已清理，以成功重跑日志为准。
- 前端：npm.cmd --prefix mobile test，21 文件、114 passed。类型检查、Vite 生产构建（200 modules）及 Capacitor sync 通过。首次缺工具失败未当通过结果。
- 日志：.runtime/a-integration-20261110/backend-verified.log、frontend-tests.log、android-build.log、gradle-retry.log（均忽略，不提交）。初次 Gradle 进程结束但无结果，故单独离线重试 assembleDebug；一次日志相对路径错误在执行前纠正。
- 旧 APK 已备份到 .runtime/a-integration-20261110/previous-CampusWeave-debug.apk，SHA-256 为 7B1E747E1DC85F2ED5BC7D8EF48F8E19BCEF760E270FDBD58AA5410ED4473C75。
- adb devices 未发现连接设备；本轮未安装或操作手机，未运行 instrumentation/浏览器真实 API 恢复链。现有页面脚本依赖另一工作区 Python 路径，未冒充本轮已验。
- 待设备验收：记录设备/系统/WebView、APK 与后端版本；安装与登录；后台返回/划掉任务/进程重建后的登录保持；冷热/文本/多文件分享；未确认不上传、取消和按快照清理、失败重试与重复数据。登录内存凭据缺口仍未修复，RF-006 保持进行中，公共凭据方案待评审，不用 localStorage 存长期凭据。
- 本轮不 commit/push；交叉评审和真机验收未完成。

### 本次 APK 结果

- Gradle 离线重试 BUILD SUCCESSFUL，108 tasks（66 executed、42 up-to-date），2m18s；随后按脚本相同目标手动复制新 APK。首次完整脚本未取得成功结论，成功结果来自单独 Gradle 重试。
- 路径：deliverables/CampusWeave-debug.apk；大小：9947205 字节；SHA-256：82356ABC5CED723AFC10789CEC178A0C10B2C0FE09006920C4AE2AF6CE6F4CBC。来源：d1d8647 加本轮 A 脚本/文档修改，未提交；不是签名发布版。
- flatDir、SDK XML、Vite CJS 等警告保留；构建成功不代替真机验收。


## 2026-11-12 · RF-006 人工验收补录与定向定位

### 证据与版本
- 本节依据用户本轮真实反馈补录，具体设备型号、Android/WebView版本、各场景操作时间未提供。截图曾在其他聊天提供，本仓库未取得，待归档，无虚构路径。
- 当前分支 chore/a-integration-baseline-20261110，HEAD d1d8647；本地 main/origin/main 相同。远端查询被本机代理 127.0.0.1:7897 连接失败阻断，不能保证远端无新提交。本地未发现后续修复 commit。
- 原 README、构建脚本修改及未跟踪 A.md 保留；本轮仅追加本文件。实际 APK SHA-256 再核对为 82356ABC5CED723AFC10789CEC178A0C10B2C0FE09006920C4AE2AF6CE6F4CBC，与用户测试包一致。安装到手机的包未独立提取核验。
- 历史后端223/前端114通过及构建成功只引用上一节，本轮未重跑。用户报告 server/.venv/Scripts/python.exe 启动、adb reverse 8000连接，health 200，mode=v2/backend_mode=real/analysis=local-text-only/ai.configured=false；不视作在线AI验证。

### 人工观察结果
- 初步通过：安装、启动、登录及后端页面；短时间后台返回保持登录；纯文本分享进入正确确认页；冷启动重新登录后待导入内容保留；删除重复文字后保存一条来源；分析完成并显示“已建立证据”；结果页打开并完成正式事项创建；后续一次热启动文本分享正常。
- 未通过：BUG-A01 划掉任务后重开需登录；长后台偶发失效，时长未知。BUG-A02 一次冷启动输入框出现三份相同文字，来源预览数量为1，不能写成三条服务端来源。
- ISSUE-A03 旧账号不可用，新注册账号可登录，具体错误响应未提供；原因未定。
- UX-A04 结果页过长、层级不清、技术信息多；未阻断创建，列后续交互待办，本轮不改UI。
- 未测或证据不足：设备/系统版本、长期后台边界、此次多文件/文件/图片/链接、权限拒绝、未确认零上传、按ID清理、失败重试幂等、服务端来源/证据/正式事项关系与账户隔离。界面显示与人工创建成功不能替代数据库一致性验收。RF-006 保持进行中。

### BUG-A01 定位与最小方案（未实施）
- mobile/src/core/http.ts: access/refresh是模块变量；setSession只赋值，401刷新依赖内存refresh。stores/account.ts初始化user=null；main.ts/App.vue未发现启动恢复。因此进程/WebView重建必失去客户端会话，这是明确代码缺口，与短后台正常、划掉重开失效相符；尚无生命周期和脱敏网络证据证明每次现象唯一根因。
- 最小候选：Android Keystore保护的refresh凭据保存，启动时单次恢复/刷新并恢复user，access仍在内存；轮换后原子更新、退出/撤销清理、离线失败与无效凭据分开处理。先核定现有登录/刷新响应是否足够，不默认改服务端协议或数据库，不用Web localStorage/普通Preferences裸存长期令牌。
- 回归：进程重建、后台超access时限、并发恢复/401、轮换写入失败、断网重试、撤销/退出/换账户、恢复期间系统分享保留。只记录生命周期、请求状态、凭据存在与否，不记录凭据值。
- A下一项优先任务：提交“Android安全会话恢复”最小技术方案评审，再实施；涉及公共认证生命周期、原生安全存储及账户隔离，须按A/B公共技术与相关负责人交叉评审规则确认，非A自行签认。本轮未安装依赖、未改认证业务。

### BUG-A02 定位与最小方案（未实施）
- ImportView.vue:20/26–38：shareIds/readingShared是组件局部状态；onMounted及share查询变化读取原生队列，以ID过滤后直接追加draft.text。draftStore.ts的Pinia草稿跨页面挂载保留，而已读ID不随草稿保留；离开再进入时旧队列可再次追加。队列仅保存成功或主动丢弃后清理。这是可推导的重复追加路径，尚未真机稳定复现本次三份文本。
- loadShared先追加文本，再await读取文件，最后登记ID；混合分享文件读取失败时ID未登记，重试可能再次追加文本。
- ShareReceiverActivity.onCreate不检查重建状态，onNewIntent也enqueue；每次生成新UUID。PendingImportStore.append直接追加，缺少同一次投递恢复幂等保护。原生重建/重复投递是另一待验证路径，不可用内容相同一律去重（用户可能主动再次分享相同内容）。
- App.vue启动及pendingImportsChanged都会导航，需结合页面重挂载事件核实；插件事件本身只通知，不直接追加文本。draftStore对整个非空text始终生成一条来源，故预览1不能证明原生队列只有1项，也不能证明服务端重复创建。
- 最小候选：让已吸收的队列ID与草稿同生命周期管理，读取/合并失败保持一致，保存/取消仅确认对应ID；原生投递去重单独验证后再改。不提前清队列、不按文本hash吞掉新分享。
- 回归：一个队列ID反复读取/页面重挂载/登录往返不重复；不同ID相同文字保留；混合文件读取失败后重试；保存清理失败后重试；连续新分享与按快照清理；Activity重建与冷/热分享。修改涉及分享协议/消费确认时先评审并运行原生及移动端相关测试。本轮不宣布修复。

### ISSUE-A03 安全检查
- 只读源码与文件元数据，未连接SQLite、读取账户记录、输出密码/token/Cookie/资料或执行初始化/迁移。
- settings.py默认real数据库为server/data/ruleflow.db；DATABASE_PATH覆盖，显式相对值按启动cwd解析；DEMO_MODE选择另一数据库。当前检查进程未设置这三个路径/模式环境变量，不能据此推出用户服务进程环境。
- 实际存在server/data/ruleflow.db（536576字节，检查时mtime 2026-11-11 11:05:20）及.runtime/http-smoke/ruleflow.db（536576字节）。不以大小相同认定内容相同。
- android-usb-test.ps1 Server指定.runtime/android-usb/ruleflow.db；start-deepseek-backend.ps1指定.runtime/deepseek/server/ruleflow.db。本次未在这些位置找到ruleflow.db。Python解释器一致不代表数据库路径一致；health real也不指明具体数据库。
- USB脚本每次生成refresh pepper会影响旧会话，但密码验证采用Argon2，不能用pepper变化解释旧账号密码登录失败。需核对原/本次启动方式、进程实际DATABASE_PATH与登录错误码；仍不读取真实账户内容。本轮无账号丢失或库损坏结论。
- 顺带发现USB脚本Prepare仍复制旧名Zhishi-RuleFlow-debug.apk，与当前构建目标名不一致；登记A脚本兼容待办，勿用Prepare选错旧包，本轮不改脚本。

本轮仅记录与只读定位，无业务改动、构建、测试、提交、推送或PR；未修改其他成员记录或任务安排。

## 2026-11-12 · RF-006 Android安全会话恢复本地实现

- 基线仍为 chore/a-integration-baseline-20261110 / d1d8647。本地没有用户提及的a408d0a；远端代理连接失败，fetch提权首次审批超时，未合并新主线。原README/构建脚本修改及既有A.md保留。未提交、推送、创建PR。
- 根因沿用前述定位：内存token和无启动恢复；服务端access为15分钟，refresh默认30天，refresh撤销同family旧会话并轮换。服务端数据库、Pepper变化会令旧会话无效，不由客户端绕过。
- 实现文件：core/http.ts、core/native/credentials.ts、stores/account.ts、main.ts；原生SessionVaultPlugin.java及MainActivity注册；core/session.test.ts、stores/account.session.test.ts。
- 原生存储：AndroidKeyStore的RSA-2048私钥不导出；RSA/ECB/PKCS1Padding仅包裹每次随机生成的AES-256密钥，AES/GCM/NoPadding认证加密refresh正文；AtomicFile写入noBackupFilesDir，现有allowBackup=false保留。仅持久化密文和包裹密钥，不持久化access，不使用Preferences明文。读不到密钥、密文损坏时清理并报告重新登录；写入失败明确报错。清理删除专用密钥，应用清数据后无恢复来源。
- 方案取舍：Keystore直接AES需要API23；为保留minSdk22采用标准JCA混合加密调用，无手写密码算法、无新依赖。代价是本项目负责文件格式/异常恢复及旧设备兼容验证；不是经过独立密码学审计的通用保险库。RSA旧API有弃用编译提示。参考Android官方KeyGenParameterSpec API文档：https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec 。上线前重点评审API22实际provider行为、无备份目录及OEM迁移、密钥失效处理。
- HTTP：保留现有协议/单飞刷新；比较请求发出时access避免迟到401再次轮换；epoch防止退出后迟到结果发布会话；凭据写操作串行；先可靠保存轮换结果再发布access；网络/429/5xx保留凭据，明确401清理；启动恢复单飞，使用account/settings恢复id/email后才设置user。恢复刷新和身份请求有15秒超时。Web保持内存会话，无持久化。
- Account：退出立即清空身份和关联UI状态；操作序号阻止迟到恢复覆盖退出/新登录；保持原owner workspace退出删除语义。启动在路由挂载前恢复会话，失败仍挂载应用，错误放入account.error。未修改分享或页面布局。
- 验证：npm.cmd --prefix mobile test -- src/core/session.test.ts src/core/http.test.ts src/stores/account.session.test.ts src/stores/dashboard.test.ts src/features/imports/batchStore.test.ts：5文件25通过。包括登录保存/保存失败、重新读入与身份、轮换、并发401、网络/429/500、401清理、密钥错误Mock、退出迟到响应、账户隔离。npm.cmd --prefix mobile run build：最终vue-tsc/Vite通过（201 modules）；中途account括号错误经类型检查发现并修正。git diff --check最终通过。
- Android：JDK17/既有SDK，gradlew.bat compileDebugJavaWithJavac --offline --no-daemon，初次缓存锁拒绝访问，提权重试BUILD SUCCESSFUL，46 tasks，1 executed。仅Java编译，无新APK打包；已有deliverables/CampusWeave-debug.apk仍是旧基线，不可用于验证本修复。
- 未验证：Android22及现代系统真实加解密、密钥失效/密文损坏/备份恢复/清数据、进程重建、后台长驻、真实服务器轮换及原生桥错误。Mock不是Keystore或真机验收。本轮未跑分享全套/后端全量测试，未操作真实账号或数据库。
- 保留协议边界：服务端已轮换但响应丢失、或轮换成功后本机无法可靠保存，可能必须重新登录；不重用旧refresh、不改服务端协议。若设备存储及Keystore清理同时失败，只能明确报错，不能保证跨进程清理成功。稳定数据库与Pepper是跨服务端重启保留会话的前提。
- 待交叉评审：上述加密封装及API22兼容、存储失败与退出清理、启动错误体验、与a408d0a及后续主线的定向兼容；之后单独打包并做Android会话恢复真机回归。RF-006不标完成。

## 2026-11-12 · RF-006 定向代码评审与小修复
- 基于当前diff及新增文件审查，保留全部既有未提交内容，不重新设计认证或改服务端。
- 已修：SessionVaultPlugin原先只检查主文件存在，会跳过AtomicFile旧式.bak恢复；现允许readFully恢复备份。写入增加显式fd.sync及读回字节一致性检查，避免仅凭finishWrite返回判成功；写入异常仍调用failWrite。GCM显式指定SecureRandom生成12字节nonce及128位认证标签，与读路径一致。
- 已修：http.apiBlob原先仅在响应头时检查epoch；读取body期间退出仍可能返回旧账户blob，现读取完成再次检查，新增回归。
- 已修：启动恢复失败没有应用内自动重试触发；main增加online事件，仅对网络/Abort/429/5xx恢复失败触发恢复；store记录retryable并在登录/退出清零，成功清除旧错误，损坏凭据不自动重试。NETWORK_ERROR作为客户端错误码保留。后端恢复但没有online事件时可重开App重试，不声称后台持续探测。
- 审查结果：凭据写操作串行，epoch和store操作号防迟到写回；身份完成前user为空；Web不写原生存储；owner workspace删除语义保留。未发现明文进入日志/普通持久化，异常仅固定文案。密钥和密文清理同时失败仍须报错，不能保证故障存储跨进程恢复状态。
- API22调用路径使用KeyPairGeneratorSpec/RSA Keystore及软件AES-GCM，未误用API23 Keystore AES生成。JCA调用检查和编译不等于设备验证。官方核对：https://developer.android.com/reference/android/security/KeyPairGeneratorSpec 、https://developer.android.com/reference/android/util/AtomicFile 。noBackupFilesDir及allowBackup=false保留，OEM备份迁移仍待实测。
- 本轮受影响测试：npm.cmd --prefix mobile test -- src/core/session.test.ts src/stores/account.session.test.ts src/core/http.test.ts，3文件24通过；较原测试新增blob迟到、恢复重试、重试标志退出清除及损坏凭据不重试。未重跑无影响的dashboard/batch测试，沿用此前通过记录。
- Android compileDebugJavaWithJavac --offline --no-daemon：BUILD SUCCESSFUL，46 tasks/1 executed；保留flatDir、SDK XML、弃用API警告。原生失败注入、磁盘回滚、API22与现代设备加解密、杀进程恢复仍未真机验证。
- 协议限制不变：refresh已轮换但响应丢失可能需重新登录；Pepper/数据库变化也可使会话失效。本轮未改协议。
- 已具备生成用于定向真机验证的Debug APK的本地条件，不代表发布放行；本轮未打包APK、不提交/推送/PR。

## 2026-11-12 · RF-006 修复后 Debug APK 完整构建

- 源码分支：chore/a-integration-baseline-20261110；HEAD：d1d8647beb6710b4e51877b18354399da3077d7c，加当前未提交的安全会话恢复与评审小修复。不是纯HEAD构建，不声称已合入远端。
- 构建前后git status清单一致：6个已跟踪修改（README、MainActivity、http.ts、main.ts、account.ts、build-android.ps1），5个未跟踪文件（本记录、SessionVaultPlugin、credentials封装和两份session测试）。现有成果保留，无额外业务或服务端修改；清单位于.runtime/rf006-session/build-package/status-before.txt、status-after.txt。
- 旧交付包9947205字节，SHA-256：82356ABC5CED723AFC10789CEC178A0C10B2C0FE09006920C4AE2AF6CE6F4CBC。构建前复制到.runtime/rf006-session/build-package/previous-CampusWeave-debug.apk，哈希已核对。
- 构建命令：仅本次进程设置JAVA_HOME=C:\Program Files\Java\jdk-17、ANDROID_HOME及ANDROID_SDK_ROOT=D:\Android\Sdk，前置对应bin至PATH，然后执行 & scripts/build-android.ps1。使用已有Gradle缓存并获得提权执行授权以避开已知缓存锁限制；未改全局配置、未清缓存、未加-WithTests。
- 实际结果：vue-tsc/Vite生产构建通过（201 modules），Capacitor sync通过，Gradle assembleDebug BUILD SUCCESSFUL in 32s；108 tasks：25 executed、83 up-to-date。完整脚本退出0；日志.runtime/rf006-session/build-package/build.log。
- 新包：deliverables/CampusWeave-debug.apk；大小：9894916字节；SHA-256：65BA36FE4CF44EB4685A18557AA38524566A020E787BBFF82038B9656A45DF9A。与mobile/android/app/build/outputs/apk/debug/app-debug.apk SHA-256相同，与旧包不同，确认交付目标已更新。
- 用途：RF-006安全会话恢复修复后的Debug真机测试包，已具备安装测试条件；尚未安装到手机或操作真实账户，不宣称会话恢复/API22/真机验收通过。
- 未重复单元测试，未改服务端、数据库、协议，未提交/推送/PR。保留构建过程Vite/flatDir/SDK相关警告，不以构建成功取代设备验证。

## 2026-11-12 · BUG-A01 新版 APK 人工真机回归未通过，暂缓处理

- 证据来源：A 本轮提供的真实人工真机反馈，非 Codex 本轮重新操作设备。设备为三星手机，具体型号、系统/WebView版本及操作时间未提供；设备品牌仅为测试环境信息，不作为失败原因。截图/日志未取得，不虚构证据路径。
- 测试版本：据A反馈为本轮新版APK，构建证据沿用上一节：deliverables/CampusWeave-debug.apk，SHA-256为65BA36FE4CF44EB4685A18557AA38524566A020E787BBFF82038B9656A45DF9A。本轮未从设备提取安装包独立核验。

| 场景 | 人工实际结果 |
|---|---|
| 正常安装和登录 | 通过 |
| 从最近任务划掉后重新打开 | 失败；未保持登录，直接进入登录页面 |
| 强行停止后重新打开 | 失败；未保持登录，直接进入登录页面 |
| 其他恢复场景 | 尚未验证 |

**BUG-A01 当前状态：代码修复已实施，但真机回归未通过，原因待定位。** Android安全会话恢复代码已实现、已有自动化测试通过，但不能据此标记问题已修复。具体失败环节尚未定位，不归因为三星设备。

按A明确要求，本问题暂缓继续修复，转入后续待办；保留已有代码、测试结果和新版APK构建证据，不回滚、不继续反复尝试修复、不扩展到其他模块。RF-006整体仍未完成验收。

本轮仅追加本记录，未修改代码、运行测试或构建、操作设备、提交、推送或创建PR。停止BUG-A01相关工作，等待A的下一项任务。

## 2026-11-19 · 恢复持续开发记录与归档后成果补录

### 记录恢复与当前状态

- 本节为恢复当日补录，不改写此前开发过程。历史正文恢复自本地 `.runtime/a-archive-20261112/original/docs/development/records/A.md`；原始备份未修改，另有 `backup/A-rf006-unverified-20261112` / `344d2cc` 开发快照。此前“未提交”等描述是各节当时状态。
- 本文件恢复为 A 持续维护的正式开发工作记录；后续任务在此增量追加，供比赛技术报告、开发文档和测试文档引用，不再作为临时文件归档后停止维护。开头的 2026-11-08 状态保留为历史描述，当前状态以本节及后续记录为准。
- RF-006：已有开发、自动化测试及 APK 构建证据，但 BUG-A01 划掉任务/强行停止后重开均未保持登录，真机验收未通过，仍未完成。认证修复仅在归档快照中，本次没有恢复未验收代码。
- UX-A04 仍为已登记、尚未实施的页面体验问题。2026-11-18 定向核对复用了历史记录和代码；仅给出结果页信息分层建议，没有实施或新增测试，不计为功能交付。

### RF-007 FileProvider 权限收窄（2026-11-18 成果，今日核实补录）

- 实际提交：`704a620988101119433c6f6105d09a1760f9c85f`，分支 `fix/RF-007-fileprovider-roots`；[PR #20](https://github.com/Hanxx1/RuleFlow/pull/20) 已于北京时间 2026-11-18 21:24 合入 main，合并提交 `a7d59866197782d04cf2dbcd7031f8f16d7566c9`。本轮通过 GitHub PR 元数据及本地提交差异核实，不把合并等同于整卡验收。
- 修改 `mobile/android/app/src/main/res/xml/file_paths.xml`：移除整个 external/cache 根目录的共享配置，限定为应用外部文件目录的 `Pictures/`（相机输入）和缓存 `exports/`（输出文件）。未扩大为文件导出或提醒完整业务实现。
- 修改 `ShareReceiverInstrumentedTest.java`：合成分享文件改放 `cache/exports/`；新增 `providerRejectsFilesOutsideExportDirectory`，断言缓存根目录下、导出目录外的文件无法生成 FileProvider URI。该提交共 2 文件，14 行新增、4 行删除。
- 测试证据核实（2026-11-19）：根据 A 提供的位置读取本地 `<PROJECT_ROOT>/../rf007-adb-instrumentation.log`，确认 AndroidJUnitRunner 对 `ShareReceiverInstrumentedTest` 输出 `OK (4 tests)`；四项均有成功状态，分别为原始文件路径拒绝、多文件 ContentResolver 读取与快照清理、URL 离线入队、导出目录外文件拒绝。保留此前 ADB 真机仪器测试四项通过的结论；本轮仅复核日志，未重新运行测试。日志本身未记录设备型号、完整启动命令或安装包哈希，不能据此独立绑定具体设备及 APK/提交版本，也不外推完整文件输出、提醒或 RF-007 整卡验收通过。原始日志留在本地，不纳入公开提交。

### 本次公开内容检查与差异边界

- 历史正文仅将一处个人项目绝对路径替换为 `<PROJECT_ROOT>`，不改变历史事实；原始备份保留原文。通用 JDK/SDK 环境路径、公开文档链接、提交 SHA 和 APK 哈希作为技术证据保留。
- 检查未发现真实账号邮箱、密码、Token/Cookie 值、设备序列号或私人业务资料。文中的 token 等为技术名称，三星为历史环境品牌描述，不是唯一设备标识；未引入原始日志、数据库或上传资料。
- 本轮仅恢复和追加 A.md，未改 B/C/D 记录、业务代码或原始备份。独立分支 `docs/RF-006-restore-a-record` 从已合入 PR #20 的 `704a620` 工作分支建立；尚未提交或推送，待 A 检查差异后确认。