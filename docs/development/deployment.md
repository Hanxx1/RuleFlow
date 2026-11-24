# 部署

1. 复制 `.env.example` 为 `.env`，生成不可预测的 `REFRESH_TOKEN_PEPPER`，填写真实 HTTPS 前端来源。
2. 运行 `docker compose up -d --build`。API 只绑定宿主机 `127.0.0.1:8000`，应由 Caddy/Nginx 反向代理并终止 TLS。
3. 持久数据位于具名卷 `ruleflow-data`。升级前按下节同时备份 SQLite、Document 原件和 Vault 原件，在隔离目录读回后再发布。
4. 将移动端 `VITE_API_BASE` 指向正式 HTTPS API 后重新构建三端包；不得把密钥打入客户端。
5. 生产注册验证/密码重置必须接 SMTP；未接入时保持注册关闭或由受控管理员发放账号。

## 单实例停写备份与隔离恢复（RF-051）

使用 Python 3.11+ 标准库，从仓库根目录运行。以下路径是执行脚本的维护环境可见的文件系统路径。`/data` 表示已挂载的正式数据卷；容器内路径需要先在维护环境中提供对应挂载。Compose 默认布局为 `ruleflow.db`、`document_uploads/` 和 `vault_uploads/`。若服务设置了 `DOCUMENT_UPLOAD_ROOT`，给 backup 追加 `--document-root /实际挂载目录`。工具不加载服务的 .env。确认输入均对应同一正式实例，Demo 和本机 Workspace 单独管理。

1. 预先创建仓库外的私有备份父目录和恢复父目录。POSIX 建议权限 0700；Windows 先检查父目录 NTFS ACL，仅授予运维账户和必要管理员访问权限。备份含完整账户库、会话记录及用户原件，清单中的资源标识也应保密。副本和恢复目录均按正式数据管理；勿放入公共共享盘、Git 或测试报告。
2. 停止 API 和一切写库、写文件进程（Compose 单实例可用 `docker compose stop api`），或提供在停写状态取得的独立卷副本。确认参数只记录操作者的停写承诺；从复制开始到 backup 成功期间须保持停写。不要手工移除 SQLite 的 WAL。备份和恢复过程中均须独占所选目录，保留足够空间。输出位置指定一个尚不存在的子目录。

```sh
python scripts/server-data-backup.py backup --writers-stopped --data-dir /data --output /private/backups/run-01
python scripts/server-data-backup.py verify --backup /private/backups/run-01
python scripts/server-data-backup.py restore --backup /private/backups/run-01 --output /private/rehearsals/run-01
```

3. 三个命令成功均返回 0，输出 Document 目录（含脱敏副本）及 Vault 目录的文件数。失败返回非零并显示错误类别。若报 `DOCUMENT_MISSING`、`DERIVATIVE_MISSING` 或 `VAULT_MISSING`，先核对挂载和原实例。已有引用但缺件时应保留现场；不要补空文件或改数据库来通过验证。工具检查 SQLite 完整性、外键、必要业务表及读取所需字段。Document 的大小和 SHA-256 与入库记录核对，解析失败的原件也包括在内。每条 `document_derivatives` 记录按所属账户和副本 ID 对应到 Document 目录中的文件，其 SHA-256 须与副本入库摘要相符。Vault 现有元数据只支持核对大小，清单摘要从此次备份建立，用于发现之后的字节变化。

   v2 清单的 `created_at_utc` 是生成备份清单时的 UTC 时间。`database_migration_version` 取自库副本的 `MAX(schema_migrations.version)`，核验时重新读取。迁移 10 起必须存在脱敏副本表。单靠数据卷无法确定运行服务的源码提交，`source_revision` 记为 `null`。已有 v1 清单仍可核验和恢复，同样检查库结构及脱敏副本。清单未经签名，须通过受控存储维护其可信性。
4. 在隔离服务中将 `DATABASE_PATH`、`DOCUMENT_UPLOAD_ROOT`、`VAULT_UPLOAD_ROOT` 分别指向恢复目录下的同名库及两个子目录，沿用匹配的服务配置和安全凭据。确认演练实例无法读取原卷，使用授权测试账户按旧 ID 读取原件、证据行及任务关联，再验证另一账户被拒绝。需要原服务继续运行时，由运维人员确认其仍指向原卷，再按原配置启动。此工具仅生成独立恢复目录；真实卷切换另行安排。

## AI 辅助分析（可选）

AI 只在服务端调用，模型密钥不进入前端、APK 或 Git。模型负责从脱敏证据块提取候选规则、材料、任务和待核对问题；服务端仍会校验 `shared/rule_ast.schema.json`、EvidenceRef，并使用本地三值规则引擎计算结果。

DeepSeek 可直接使用 OpenAI 兼容接口。PowerShell 示例：

```powershell
$env:LLM_BASE_URL = 'https://api.deepseek.com/v1'
$env:LLM_MODEL = 'deepseek-chat'
$env:LLM_API_KEY = '在 DeepSeek 控制台创建的服务端密钥'
$env:LLM_TIMEOUT_SECONDS = '25'
E:\DevTools\PythonPortable\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

也可以把这几个变量放在服务端启动脚本或部署平台的密钥配置中。当前账户是否免费、是否有试用额度以 DeepSeek 控制台为准；应用不会自行伪造额度或把密钥打包进 Android。没有配置 `LLM_BASE_URL` 和 `LLM_MODEL`，或模型超时/返回非法结构时，事项页会明确显示本地规则分析或已回退，不会冒充 AI 结果。

当前镜像采用单实例 SQLite，适合比赛演示和小规模试用。多实例生产部署需先迁移到 PostgreSQL 和正式迁移工具，不能共享 SQLite 文件运行多个副本。
