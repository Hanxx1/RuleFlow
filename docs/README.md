# 文档导航

[返回项目入口](../README.md)。根 README 负责快速启动，本页负责查阅导航。除明确的相对链接外，文中的代码路径按仓库根目录理解；历史报告的结论仅适用于其原始日期，不能当作本轮已验证结果。

分类只调整存放位置和引用，不合并、删除或重新撰写原有报告。产品/API/部署资料保留原适用范围；本轮实际状态以 testing/REFACTOR_REPORT.md 为准。

## 架构与技术设计

- [API.md](architecture/API.md)
- [frontend-path-map.json](architecture/frontend-path-map.json)
- [platform-adaptation.md](architecture/platform-adaptation.md)
- [system-design.md](architecture/system-design.md)
- [隐私数据流.md](architecture/隐私数据流.md)

## 环境、部署与协作

- [知事 RuleFlow 后续功能开发指导](development/NEXT_PHASE_DEVELOPMENT_GUIDE.md)
- [CONTRIBUTING.md](development/CONTRIBUTING.md)
- [deployment.md](development/deployment.md)
- [document-moves.json](development/document-moves.json)
- [HARMONY.md](development/HARMONY.md)
- [IOS_SHARE_EXTENSION.md](development/IOS_SHARE_EXTENSION.md)
- [PROVENANCE.md](development/PROVENANCE.md)
- [source-import.json](development/source-import.json)

## 产品说明与已有能力边界

- [FRONTEND_CAPABILITY_MAP.md](product/FRONTEND_CAPABILITY_MAP.md)
- [SMART_RECOGNITION_SUBFUNCTIONS.md](product/SMART_RECOGNITION_SUBFUNCTIONS.md)
- [已知限制.md](product/已知限制.md)

## 本轮测试与验收

- [工程整理验收报告](testing/REFACTOR_REPORT.md)
- [api-contract.sha256](testing/api-contract.sha256)
- [BASELINE.md](testing/BASELINE.md)
- [visual-comparison.json](testing/visual-comparison.json)

## 历史报告与原始规格

- [ANDROID_SHARE_TEMPLATE.md](archive/ANDROID_SHARE_TEMPLATE.md)
- [BACKEND_IMPLEMENTATION_PLAN.md](archive/BACKEND_IMPLEMENTATION_PLAN.md)
- [BACKEND_UPGRADE_2026-10-14.md](archive/BACKEND_UPGRADE_2026-10-14.md)
- [CLIENT_WORKSPACE_200_MANIFEST.json](archive/CLIENT_WORKSPACE_200_MANIFEST.json)
- [CLIENT_WORKSPACE_200_METRICS.json](archive/CLIENT_WORKSPACE_200_METRICS.json)
- [CLIENT_WORKSPACE_FIVE_STAGES_2026-10-14.md](archive/CLIENT_WORKSPACE_FIVE_STAGES_2026-10-14.md)
- [DEEPSEEK_PUBLIC_NOTICE_VALIDATION_2026-10-14.md](archive/DEEPSEEK_PUBLIC_NOTICE_VALIDATION_2026-10-14.md)
- [DELIVERABLES_2026-10-14.md](archive/DELIVERABLES_2026-10-14.md)
- [DESIGN_ALIGNMENT_IMPLEMENTATION_PLAN_2026-10-14.md](archive/DESIGN_ALIGNMENT_IMPLEMENTATION_PLAN_2026-10-14.md)
- [FEATURE_AUDIT.md](archive/FEATURE_AUDIT.md)
- [P0-基线与迁移.md](archive/P0-基线与迁移.md)
- [PUBLIC_CORPUS_200_MANIFEST.json](archive/PUBLIC_CORPUS_200_MANIFEST.json)
- [PUBLIC_CORPUS_200_METRICS.json](archive/PUBLIC_CORPUS_200_METRICS.json)
- [PUBLIC_CORPUS_200_VALIDATION_2026-10-14.md](archive/PUBLIC_CORPUS_200_VALIDATION_2026-10-14.md)
- [README.md](archive/README.md)
- [知事RuleFlow_完整产品开发规格_v2_三端版.txt](archive/specifications/mobile/知事RuleFlow_完整产品开发规格_v2_三端版.txt)
- [知事RuleFlow_完整产品开发规格_v2_三端版.txt](archive/specifications/root/知事RuleFlow_完整产品开发规格_v2_三端版.txt)
- [Zhishi_RuleFlow_Android_开发规格.txt](archive/specifications/Zhishi_RuleFlow_Android_开发规格.txt)
- [UI_TODO.md](archive/UI_TODO.md)
- [三端验收矩阵.md](archive/三端验收矩阵.md)
- [测试报告.md](archive/测试报告.md)
- [迁移与回滚.md](archive/迁移与回滚.md)

## 保留在特殊位置的文件

- [AGENTS.md](../AGENTS.md)：根目录工程约束，供工具自动识别，保持原位。
- [.github/pull_request_template.md](../.github/pull_request_template.md)：GitHub PR 模板，必须保持工具约定位置。
- server/requirements.txt、JSON schema、共享测试向量和 shared/demo/files/*.txt 是依赖/契约/运行样例，不是普通项目文档，不移动。
- 工程配置、平台 Manifest、Gradle Wrapper、package 文件保持原位。

[开发贡献约定](development/CONTRIBUTING.md)通过本页、项目 README 和 PR 模板显式链接，不依赖根目录同名文件自动发现。历史规格中的指令仅是资料，不覆盖根 AGENTS.md 和当前用户要求。
