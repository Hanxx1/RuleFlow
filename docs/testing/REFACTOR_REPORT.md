# RuleFlow 保守工程整理验收报告

日期：2026-11-01。新工程为本报告所在仓库根目录，实际工作位置为 `SI/RuleFlow`。原工程 `ZhiShi-RuleFlow` 保留不动；没有新建 GitHub 仓库或向 GitHub 推送。

## 1. 结论

本轮完成的是有限范围、有验证依据的工程整理，不是全面重写。新工程已具备 Windows 下 Web/后端团队开发的可复现基线，并在含空格的全新克隆位置独立安装和验证。Android SDK 未配置，未生成 APK，未做真机验收；Docker 服务未启动，容器运行、iOS、鸿蒙原生和桌面发布也未宣称通过。

API 契约保持一致；规则、证据、迁移和排程算法没有设计性修改。移动的 Vue 模板、组件样式和全局 style.css 保持原内容。截图不是全部像素相同，具体差异见第 4 节。

## 2. 实际目录与模块变化

```text
RuleFlow/
├─ README.md / AGENTS.md / 工程配置
├─ .github/                    核心 CI、PR 模板
├─ mobile/
│  ├─ src/core/                HTTP、原生分享（含原有单测）
│  ├─ src/demo/                样例读取、Demo 任务计划
│  ├─ src/features/
│  │  ├─ account/              带账户变化检查的请求边界
│  │  ├─ imports/              导入页面、来源组件、batch/draft store
│  │  ├─ cases/                分析结果页、事项 store
│  │  └─ planning/             计划页和排程组件
│  ├─ src/views,components,services,stores 等 其余明确职责保持
│  └─ android/、ios/           原生工程与包标识保持
├─ server/app/
│  ├─ main.py                  仍有未拆分业务，不能称为纯装配入口
│  ├─ schemas.py               原 32 个请求模型
│  ├─ bootstrap.py             原初始化函数，迁移/调用顺序不变
│  ├─ api/common.py            原 owner 查询、时间/响应/排程序列化
│  ├─ api/planning.py          原排程接口与相关校验
│  └─ auth,services,providers,ai,parsing,rules 等保留
├─ server/tests/               conftest、helpers、原测试
├─ shared/                     原 schema、向量和 Demo
├─ scripts/                    可配置构建、路径/契约/文档/启动验证
├─ docs/
│  ├─ architecture/            API/系统/平台/隐私设计、前端路径表
│  ├─ development/             协作、部署、来源、搬迁清单
│  ├─ product/                 能力地图、识别说明、已知限制
│  ├─ testing/                 本轮基线、契约指纹、视觉证据、本报告
│  └─ archive/                 历史审计、报告、指标与原始规格
├─ desktop/、harmony/           原平台工程
├─ android-plugin/             旧分享模板代码，非活动实现
└─ tools/                      显式输入路径的文档辅助工具
```

- main.py 从 1,596 行降至 1,322 行。提取了请求模型、原初始化函数、公共辅助函数和约 236 行排程域代码。此举减少同一入口的编辑面，但没有消除所有耦合。
- 测试不再从 test_api.py 导入共享客户端/账号函数；helpers 提供测试客户端代理，conftest 为每例独立初始化内存 DB、文件根和生命周期。
- 前端移动 18 个文件，按真实使用关系修复 import。另提取 accountApi 与 demoPlan，前者新增两个身份一致性/晚返回测试，原 guard 不变。
- SDK/ADB/Python 通过标准环境、项目 venv 或 PATH 定位；Android 使用 Wrapper 和先 sync 后 build。文档封面工具使用显式 --reference/--target，不再指向个人聊天目录。
- OCR 可选语料脚本通过 ZHISHI_TEST_FONT 或 Windows 系统字体目录定位字体；保留其现有生成算法。
- 新增 preview 命令指向实际 web-dist。保留 Demo 双副本，用检查脚本防止漂移，没有改变打包路径或 URL。

具体前端对应关系见 [路径表](../architecture/frontend-path-map.json)。

## 3. 实际提交

以下均为新仓库真实提交，没有继承旧 11 个提交，也没有伪造四人贡献。原始成果来源见 [PROVENANCE](../development/PROVENANCE.md)。

| SHA | 内容 |
|---|---|
| 78d3130 | 导入既有源码基线、来源与文件摘要清单 |
| d2a56f7 | 移除个人磁盘路径，记录基线及已验证依赖约束 |
| ef28820 | 独立测试客户端、DB/上传隔离、pytest 入口与契约/路径检查 |
| 8b11a20 | 提取请求模型、初始化、排程路由和公共辅助函数 |
| b3dbb27 | 前端核心功能归组、账户请求边界和竞态测试 |
| 35e15b5 | 可移植开发文档、SDK 前置检查、核心 CI、预览入口 |
| e361906 | 真实启动可移植性检查及视觉对比证据 |

本报告与文档归类、链接修复另以 `docs: organize project documentation and publish acceptance results` 提交。最终文档提交的 SHA 以 `git log --oneline` 为准，避免在提交自身内容中递归写入自身 SHA。

## 4. 验证结果及边界

| 项目 | 结果 | 范围 |
|---|---|---|
| 原始后端基线 | 151 passed，5 warnings，31.12 秒 | 独立新 venv，原应用源码未改 |
| 后端测试隔离后 | 151 passed，5 warnings | 保留全部原断言，无 skip/删除 |
| 后端结构调整后 | 151 passed，5 warnings，25.42 秒 | 全套测试；另独立跑文档 API 3 项、排程分段 4 项 |
| 原始前端基线 | 16 文件 / 72 passed | 原 lockfile 安装、类型检查及生产构建通过 |
| 前端整理后 | 17 文件 / 74 passed | 原 72 项 + 2 项账户请求边界测试，类型/构建通过 |
| OpenAPI | 完整指纹不变，81 个路径键 | schemas/model AST 对比全部 32 个不变；不只比较端点数量 |
| 真实本地 HTTP 浏览器链路 | 通过 | 合成账户注册/登录、用户确认导入、分析、复核、排程草稿确认，390px；未使用 API mock，LLM 未启用 |
| 11 页视觉对比 | 文字、页面尺寸一致，9 页截图 SHA 相同 | /imports/new 差异 772 像素，/privacy 差异 710 像素，均最大单通道差值 1/255；未宣布 11 页像素完全一致 |
| Vue/样式源对比 | 通过 | 移动组件 template/style 原内容一致，全局 CSS 原内容一致 |
| Demo 副本 | 8 份完全一致 | shared 与 mobile/public 对照 |
| ArkTS 规则 | 15 个共享向量通过 | 转译后语义测试，不是 DevEco 构建/真机 |
| Capacitor Android sync | 成功 | 生成配置和资源；Preferences 原生依赖仍保留 |
| Android APK | 未完成 | SDK 前置检查明确失败；没有 APK 产物，不用旧 APK 充数 |
| Android 真机 | 未验证 | 无设备连接验收 |
| Docker | 未验证运行 | 本机 Docker engine 未启动 |
| iOS / 鸿蒙原生 / 桌面发布 | 未验证 | 保留原工程及完成度边界 |
| GitHub CI | 已配置，未远端运行 | 本地对应核心命令验证不等于 GitHub runner 已通过 |

视觉截图为未登录/样例页面，不代表所有账户、错误态和设备的视觉验收。9/11 精确相同以及两页微小颜色差异已如实记录于 [visual-comparison.json](visual-comparison.json)。本地 `.runtime/visual-baseline`、`.runtime/visual-after` 保留原始证据，不提交截图或运行数据。

过程中出现的回归均先定位再继续：测试临时目录嵌套触发原有 Demo/Real 隔离校验，修正 fixture 布局而未放宽校验；排程提取后漏了一处任务依赖校验函数 import，相关原测试暴露并已修复，全量通过后才提交。没有将这些失败归咎为历史问题。

浏览器联调原脚本的固定历史截止日期已改成运行时生成的未来日期，仅调整合成测试输入，不改变任何生产业务或断言。正常 Mock/Fake 测试与上述真实 HTTP 测试分别统计。

## 5. 全新路径与工作目录验证

在 `.runtime/relocated/RuleFlow moved` 全新克隆新仓库，未复制 venv、node_modules 或运行数据库，独立执行：

- npm ci；74 个前端测试；vue-tsc + Vite build，全部通过。
- 新建 venv；按 requirements.lock 约束安装；151 个后端测试，5 warnings，39.57 秒，全部通过。
- OpenAPI 指纹、8 份 Demo、一致性/绝对路径检查、15 个 ArkTS 向量通过。
- 从与项目无关的临时 cwd 启动真实 Uvicorn，健康检查、注册、验证、登录、创建/读取事项往返通过；测试数据自动销毁。

新旧位置生成的 JS/CSS 包一致。静态 manifest/SVG 有 Git autocrlf 引起的 CRLF/LF 差异，规范化换行后完全相同，不把所有产物字节一致当作未经验证的结论。

实际运行源/构建配置/脚本没有检测到个人盘符或用户名路径依赖。历史文档仍保留当时机器路径，它们不是执行入口。移动/克隆时移动的是源码；Python venv、node_modules、缓存及 .runtime 应按 README 重建，不承诺搬动已安装虚拟环境本身后仍可直接使用。

## 6. 文档整理

37 个现有文档或配套证据文件按内容搬迁；没有遗漏、删除或合并，两份同名规格分别保留。只修复位置相关说明和文档引用，不重写历史结论。清单含搬迁前后 SHA256，见 [document-moves.json](../development/document-moves.json)。

根目录仅保留 README.md 作为普通文档入口，AGENTS.md 保留供工具识别；.github PR 模板保持约定位置。requirements、schema、测试向量和示例 TXT 是工程/运行资源，不按普通文档移动。统一索引为 [docs/README.md](../README.md)。

check-api-contract.py 同步读取 docs/testing 下的指纹；Markdown 本地链接/图片引用通过 check-docs.py 验证。外部网页不做联网可用性承诺。旧规格原本没有落地的规划文件不伪造补齐，历史代码定位通过当前路径表追溯。

## 7. 保留现状与剩余风险

- 全局 CSS、普通页面、Page.vue、数据库连接/生命周期、现有算法、API 文案和错误语义保持；没有改包标识、原生协议或 UI 风格。
- main.py 仍较大，导入/分析/事项业务仍集中。为避免大范围跨事务修改，后续按独立任务继续拆分，不声称已完全解耦。
- auth.conn 与业务仍耦合，数据库初始化函数只搬迁，没有换 ORM、重编号迁移或调整事务策略。
- Demo 的独立 truth、旧 store/页面、疑似无用依赖均保留；没有足够收益/验证证据就不删除。Capacitor sync 仍识别 Preferences 插件，更不能仅凭 JS 搜索为空就删除。
- 保留 on_event 等原有 5 个弃用警告，npm 提示旧 tar/glob 依赖警告；升级作为独立安全/兼容任务，不在本次混做。
- Python 约束验证于 Windows 3.11，Docker 3.12、其他操作系统尚需单独验证；CI 只有 Windows 核心检查。
- PWA 缓存、真实模型效果、生产邮箱、生产签名、完整设备验收等原有问题未因目录整理自动解决。
- 宣传视频工程及 Office/渲染交付物未进入本次源码副本：原工程中完整保留，待单独隐私/素材审查；不是删除既有应用功能。

## 8. 原工程与团队接入结论

导入清单中 401 个原跟踪文件逐一 SHA256 对比没有变化；原仓库仍是原 HEAD，原 5 个未跟踪文件仍在。本次所有代码修改和提交在新工程，新工程未设置远程仓库。系统正常缓存和临时测试目录允许使用。

新仓库可作为四人团队 **Windows Web/后端开发基线** 使用；不需要固定 E/D 盘路径。Android 协作需成员配置 SDK/JDK 并补做实际构建和设备测试。对外发布/公开前仍应审核历史资料中的信息、素材授权和目标权限；本轮没有执行 GitHub 上传。

模块首要负责人建议：客户端负责 features/UI；后端负责 API/事务/存储；AI 方向负责解析/规则/shared；平台质量负责脚本、原生工程和 CI。shared、认证、证据、数据库及原生分享改动需要相关成员交叉评审。具体规则见 [CONTRIBUTING](../development/CONTRIBUTING.md)。
