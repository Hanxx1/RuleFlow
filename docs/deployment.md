# 部署

1. 复制 `.env.example` 为 `.env`，生成不可预测的 `REFRESH_TOKEN_PEPPER`，填写真实 HTTPS 前端来源。
2. 运行 `docker compose up -d --build`。API 只绑定宿主机 `127.0.0.1:8000`，应由 Caddy/Nginx 反向代理并终止 TLS。
3. 持久数据位于具名卷 `ruleflow-data`。升级前同时备份 `/data/ruleflow.db` 与 `/data/vault_uploads`，恢复演练后再发布。
4. 将移动端 `VITE_API_BASE` 指向正式 HTTPS API 后重新构建三端包；不得把密钥打入客户端。
5. 生产注册验证/密码重置必须接 SMTP；未接入时保持注册关闭或由受控管理员发放账号。

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
