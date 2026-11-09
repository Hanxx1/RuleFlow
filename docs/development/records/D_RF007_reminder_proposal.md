# RF-007｜D 原生提醒盘点与最小样例方案

核对：2026-11-09，d8672de及当前未提交工作区。后续已完成本机SDK/ADB复用配置，见第6节；下方初次盘点的未定位结论不再代表当前工具状态。状态：**能力盘点已完成；样例方案待评审；原生提醒未实现、设备用例未执行**。本轮不新增插件、权限或原生实现，不提交/推送。D只负责提醒子项，B文件样例不在本轮代验范围。

## 1. 当前能力与环境证据

| 检查项 | 当前事实 | 结论边界 |
|---|---|---|
| 依赖/桥 | mobile/package.json含Capacitor 6/core/android/ios/preferences，没有local-notifications或push-notifications；capacitor.settings.gradle只含android/preferences；MainActivity注册PendingImportsPlugin | 有分享接收桥，不等于有提醒桥；Preferences可做候选本机映射存储，尚未实现 |
| Android代码与Manifest | 原生Java为MainActivity/PendingImports/ShareReceiver；源码未找到AlarmManager/NotificationManager/提醒调用；主Manifest只声明INTERNET，无通知运行时权限、精确闹钟权限或启动恢复receiver | 当前应用没有完整调度/取消/恢复链；这里只读源码，未构建合并Manifest，不断言系统库内部没有其他声明 |
| 前端/后端 | 原生TS只有share封装；/settings/notifications映射通用Page，未发现通知专项逻辑；未发现reminder_id实现。填表的reminders是文案提示 | 路由/单词存在不是系统通知能力；RF-043幂等只覆盖日程提交，不等于提醒幂等 |
| Android工程 | minSdk22、compileSdk34、targetSdk34；Gradle wrapper8.2.1；appId=com.zhishi.ruleflow | 可识别配置，不等于本轮已构建或安装 |
| Java | JAVA_HOME及java -version确认Temurin17.0.20+8 | Java可用；未执行Gradle下载或构建 |
| SDK/ADB | ANDROID_HOME/ANDROID_SDK_ROOT未设置；mobile/android/local.properties未发现；Get-Command adb无结果；常见Local/Android/Sdk及C:/Android、D:/Android检查未定位SDK | 初次检查结果；后续已定位D:/Android/Sdk并配置，见第6节 |
| 设备/模拟器 | 无可执行ADB，不能运行devices核实authorized/offline状态；用户目录.android/avd未发现 | 初次未核实；后续ADB实查列表为空，用户选择本轮仅配置环境，真机授权仍未验证 |
| APK | 当前工作区deliverables未列出APK；未生成新包，旧外部产物未定位 | 尚无本轮可核对源码SHA/哈希的候选APK；计划输出路径不等于产物存在 |
| iOS | 有工程和Podfile，平台13.0，桥只有Capacitor/Preferences；当前Windows环境 | 本轮不具备Xcode编译与iOS设备验收证据，不纳入Android通过声明 |

依据文件：`mobile/package.json`、`mobile/capacitor.config.ts`、`mobile/android/variables.gradle`、`mobile/android/app/src/main/AndroidManifest.xml`、`mobile/android/app/src/main/java/com/zhishi/ruleflow/MainActivity.java`、`mobile/src/router.ts`、`scripts/environment.ps1`、`scripts/build-android.ps1`、`scripts/android-usb-test.ps1`。

构建脚本会执行Capacitor sync和Gradle；USB脚本部分动作会安装/启动/设置reverse。本轮均未执行这些动作。`Resolve-Adb`只查SDK环境变量与PATH，不解析local.properties；后续即使只填local.properties能构建，也须为设备检查提供可定位ADB。

## 2. 最小选型建议（未安装、未定稿）

优先评估与当前Capacitor 6匹配的官方Local Notifications插件，验证一条本地通知；它提供schedule/getPending/cancel及权限检查，离线调度不依赖服务器推送。另一选项是自写Android AlarmManager桥，但恢复、授权和版本兼容成本更高；当前没有证据需要自建，不选服务端推送或Web定时器冒充本地提醒。确切版本、维护风险与锁文件变更须在后续编码任务评审，不顺带升级Capacitor。

外部依据（2026-11-09读取，能力不是本仓库实测）：
- [Capacitor v6 Local Notifications](https://capacitorjs.com/docs/v6/apis/local-notifications)：本地调度、查询待触发、取消；已展示通知移除与待触发取消是不同操作。精确设置需单独检查，Doze存在限制。
- [Android通知权限](https://developer.android.com/develop/ui/compose/notifications/notification-permission)：Android13/API33及以上普通通知需要POST_NOTIFICATIONS运行时权限；授权请求与系统拒绝需单独处理。
- [Android闹钟调度](https://developer.android.com/develop/background-work/services/alarms)：精确与非精确闹钟是不同能力。首轮不承诺锁屏/节电/强制停止后的绝对准时。

建议先验证普通一次性提醒，再把精确授权作为独立条件测试，不默认添加USE_EXACT_ALARM或滥用闹钟类能力。重启是否由插件恢复、依赖何种receiver/持久化、在哪些系统下生效，必须核对所选版本源码和合并Manifest并实机验证，本轮不假设支持。

## 3. 最小样例流程与拟定状态（Q09/Q10待确认）

使用**单条合成日程**S-demo、revision1，展示“RF-007提醒样例”，正文无真实任务/课程/私人材料，附本地合成输入依据。独立测试命名空间，不把CM-005 fixture写到账户、不污染生产日程。先证明原生日程提醒行为，正式RF-048接入另做。

1. 明确显示当前平台、通知权限/渠道状态、精确能力和“尚未调度”。仅由用户点击申请权限；拒绝或关闭授权框不循环弹窗，不误报成功。系统通知权限和精确闹钟权限分开呈现。
2. 创建一次性测试提醒：用户确认后安排T0+2分钟；记录计划绝对时间、设备时区、尝试ID及返回结果，随后查询待触发队列。普通调度的等待2分钟是测试输入，不是准时承诺。重启样例用T0+10分钟留操作余量。
3. 候选映射为owner/测试命名空间＋schedule_id＋revision＋原生notification ID，具体存储/ID分配/错误字段待A/B评审。同一次操作重试只能对应一条有效通知；不能将UUID截断成整数而不处理碰撞。不同owner不可共享撤销范围。
4. 用户取消：按本条ID撤销待触发项并查询确认；若已展示，用单独的已展示通知移除策略，不混淆“已触发”和“取消成功”。重复取消应安全。失败显示失败/待核对，日程保存不回滚。
5. 改时revision2：旧提醒先撤销，再安排新提醒；中途失败显示“新提醒未建立/待重试”，保留日程和可恢复映射，不同时保留两个有效版本。晚到revision1结果不能覆盖revision2。原生平台与数据库之间不假装有分布式事务。
6. 应用重开时对比本机映射、系统待触发项及已展示项；设备重启则分别测试“不打开App”和“打开App后的核对恢复”。只有确认仍未来、所属身份有效且未取消的记录可重建；过去时间不补发一串旧提醒。取消墓碑/版本避免恢复已撤销项，具体保留策略待Q09。
7. 断网时只操作已在本机存在的合成日程及本地提醒；已调度后离线、离线新增、离线取消分别测。不宣称离线能保存尚需服务器的正式账户日程。重新联网不能重复注册。
8. 退出/换账户样例先只验证映射隔离与撤销范围；正式退出清理顺序依RF-012/Q09。提醒失败与“日程已保存”分开反馈，不伪造成功通知或资格结果。

建议结果区分：未授权/受限、请求已受理、待触发可查询、已观察展示、已取消、失败/结果未知。API返回成功不等于用户收到；getPending不在也不自动等于已展示，需要通知栏/回调/时间证据。

## 4. 验收矩阵（全部未执行）

| ID | 条件/动作 | 最小通过证据 | 当前状态 |
|---|---|---|---|
| R01 授权调度 | 前台授权后T0+2min；同键重复一次 | 队列恰一条，记录计划/实际时间；观察一条通知，不重复 | 未实现/未测 |
| R02 取消 | 触发前取消及再次取消 | 待触发查询无该ID；观察越过原时间，记录未展示；不删日程 | 未测 |
| R03 改时 | rev1改为rev2，注入安排失败再重试 | 旧ID无效，只有新版本有效；失败状态可恢复，无双通知 | 未测 |
| R04 冷重开 | 关页面/移除最近任务后重开，分别记录动作 | 映射/队列一致；未重复调度；与强制停止分开 | 未测 |
| R05 设备重启 | T0+10min后重启；到时前不打开App | 记录通知是否实际恢复与触发；无支持则明确不支持，不伪报通过 | 设备条件受阻 |
| R06 重启后打开 | 设备重启后手动打开；包含未来、已取消、过期三记录 | 仅合格未来项恢复，取消/过期不复活，不重复 | 设备条件受阻 |
| R07 首次拒权/关闭框 | Android13+拒绝或关闭授权，再保存日程 | 不调度/不报成功，日程保存独立成功；提示可手动设置，不自动反复申请 | 未测 |
| R08 授权后撤销/禁渠道 | 已调度后系统关闭通知/渠道，再回App | 识别受限，不把队列成功等同可见；恢复权限后需核对，不重复 | 未测 |
| R09 精确设置变化 | 允许/拒绝/撤销精确能力，与通知权限交叉 | 精确能力状态独立，受限如实标注；恢复策略无旧版复活 | 待选型/评审 |
| R10 已调度后离线 | 断Wi-Fi/移动网络，后台锁屏等待 | 记录计划/实际展示，无网络请求依赖；不要求后台JS存活 | 未测 |
| R11 离线新建/取消 | 合成记录已在本机，离线调度与取消 | 本地队列变化、无重复；联网后不重新生成旧提醒 | 未测 |
| R12 节电/Doze | 锁屏、节电、厂商后台限制分别记录 | 测得延迟/丢失与设置；限制不能用“已准时”掩盖 | 设备条件受阻 |
| R13 强制停止 | 用户系统设置强制停止，再等/重开 | 单独记录行为与限制；不承诺停止期间送达；重开核对无过期补发 | 设备条件受阻 |
| R14 结果丢失/崩溃 | 原生已接受但JS未收到；取消后中断；晚到旧revision | 查询/版本协调恢复；同操作不重复，已取消不重建 | 未测 |
| R15 隔离与原入口回归 | 合成owner A/B、退出/换账号；Offline Demo与PendingImports分享 | 不撤销他人ID、不暴露真实内容；拒权不影响Demo/日程；分享仍可用 | 待契约/未测 |
| R16 已展示通知 | 到时展示后取消/点开 | 区分移除展示与取消待触发；点击只到合成详情，记录完整依据 | 未测 |

每项记录设备型号、OS/API/厂商版本、APK SHA256与源码SHA、插件锁定版本、前后台/电源/网络/权限状态、计划和实际时刻、偏差、重复数、队列前后及录屏。取消类“没有出现”需给观察起止，不能仅凭瞬时截图。精度门槛由A/D在设备实验前确认；暂不设置任意秒级SLA。有限观察窗口未触发标未通过或结果未定，不证明永不触发。

设备覆盖优先一台可授权Android13/14+真机；若可得再补Android12及另一厂商。模拟器用于权限/状态回归，不能替代厂商节电/实机重启证据。iOS与鸿蒙不随Android结果自动通过。

## 5. 阻塞、后续交付及责任

- **环境 E1**：SDK/ADB定位配置已解决（第6节）；A仍需候选设备与调试授权。当前缺项目compileSdk34平台，构建/安装基线未验证，不要求RF-006全部业务关闭。
- **契约 C1**：D给Q09映射/恢复状态与用例，A/B评审原生协议、插件及Manifest范围；B核RF-012退出/存储，C核分享入口不回归。唯一状态仍在 [公共决策表](D_public_interface_questions.md)，本文件仅是提案与证据输入。
- **实现 I1**：后续获授权后才安装锁定的兼容插件、同步原生工程，检查合并Manifest/receiver、搭单条样例并运行R01–R16；不先做RF-048全量业务提醒。
- **设备检查准备**：ADB可用后先 `adb devices -l`（记录别名避免公开序列号），只读查询OS/API、包路径及候选APK哈希；安装、改权限、重启、强制停止和省电设置须在明确测试设备/窗口后执行，本轮未做。
- 产物路径仅是现有脚本约定：`deliverables/Zhishi-RuleFlow-debug.apk`、`deliverables/Zhishi-RuleFlow-usb-debug.apk`；**当前未生成/未核验，不提供存在声明**。

本轮完成源码/环境只读盘点、官方文档核对和样例矩阵；没有原生测试通过结论，没有新增依赖、运行cap sync、构建/安装APK或改权限。能力缺口只阻塞RF-007真机完成及RF-048正式接入，不阻塞已验Web/排程/固定网格。


## 6. 后续环境复用配置（2026-11-09，已完成）

用户授权检查/复用本机SDK并确认设备；ADB空列表后，用户明确选择“本轮先完成环境配置”。没有下载组件、新增插件、安装APK或启动模拟器。

- 实际SDK：`D:/Android/Sdk`；ADB路径`D:/Android/Sdk/platform-tools/adb.exe`，版本1.0.41 / 37.0.1-15733141，实际version退出0。
- 已安装平台：android-36；Build Tools 35.0.0、36.0.0；已有cmdline-tools/emulator及android-36.1镜像。项目compileSdk34所需android-34平台缺失；完整构建仍有缺口，不能将工具可用记成APK可构建。未为绕开缺口修改compileSdk/targetSdk。
- 用户级ANDROID_HOME已设为`D:/Android/Sdk`；原用户PATH保留，仅去重追加platform-tools。ANDROID_SDK_ROOT未新增（既有值为空）。旧用户环境值备份到忽略目录`.runtime/rf007-environment-before.json`，不加入版本库。
- 项目`mobile/android/local.properties`写入`sdk.dir=D:/Android/Sdk`，经`git check-ignore -v`确认被mobile/android/.gitignore第27行忽略。
- 当前验证进程加载同样的ANDROID_HOME/PATH后，dot-source现有`scripts/environment.ps1`，`Resolve-Adb`准确返回上述路径；未修改公共脚本。用户级持久值已回读核验。已打开的终端/Codex进程可能仍保留旧环境，需重开终端/应用，或在该PowerShell临时设置 `$env:ANDROID_HOME='D:\Android\Sdk'; $env:Path='D:\Android\Sdk\platform-tools;'+$env:Path`。
- `adb devices -l`两次均为空列表，没有显示device、unauthorized或offline条目；所以当前**未检测到ADB设备**，不能推断某台手机已授权，也不能断言USB线/驱动一定有问题。按用户选择不继续等待连接。
- 显式使用进程级ANDROID_AVD_HOME=`D:/Android/Avd`时，emulator -list-avds列出已有`AppFunctions_API36_1`。这是其他项目可用的AVD线索；本轮未启动/重置它，未设置全局AVD_HOME或改动其镜像。

后续：准备项目所需平台/构建工具并验证构建链；连接测试手机后再次读取devices状态，若unauthorized才由用户在手机确认调试授权。设备未测与提醒代码尚未实现仍分别保留；本轮无新APK、提交或推送。
