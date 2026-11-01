# 本轮后端升级与验收步骤

本说明适用于2026-10-14工程增量，API为/api/v1，实际迁移006–016。保留现有Case/Fact/Rule/Evidence/Task；没有要求清空数据库或替换Demo。上线操作尚未执行。

1. 在维护窗口停止写入，备份当前SQLite数据库、配置和私有原件/Vault目录；备份不可提交Git。目录需保留owner_id层级和随机文件ID，否则旧Evidence预览会失效。
2. 保留已有DATABASE_PATH/VAULT_UPLOAD_ROOT，配置DOCUMENT_UPLOAD_ROOT。明确Demo使用不同DEMO_DATABASE_PATH/DEMO_DOCUMENT_ROOT/DEMO_UPLOAD_ROOT，且双方上传根不能互相包含。检查目录读写权限、磁盘预算与服务账户。
3. 在已安装项目依赖的Python环境启动server/app/main.py。database()会幂等执行006–016；查看schema_migrations版本及健康接口，确认表存在。不要修改迁移编号、checksum或删除旧规则来消除错误。出现迁移错误立即停止启用新前端，用备份恢复对应版本。
4. 模型未配置时只做本地候选抽取；知识库为空时返回无资料而非Demo。配置在线模型须单独保管密钥并测试超时/无效引用降级。当前知识检索是本地TF-IDF摘录，没有神经Embedding服务验收。
5. 用独立测试账户导入一份陌生通知、另一份细则：核对行Evidence，确认动作/依赖/日期，补足画像；缺字段应UNKNOWN，画像硬冲突应FALSE，关注分类不能覆盖资格。测试另一个账户不能获取原件、历史、资料、草稿或脱敏副本。
6. 在任务日程填写耗时及允许拆分、限额/缓冲，导入周期课并锁定；先预览再整份确认。增加课程后旧草稿应DRAFT_STALE，任一冲突整份不保存。独立添加后置安排不能绕过前置/截止。
7. 文件先确认处理范围，扫描敏感项，选择并生成副本；检查原件hash不变、图片像素永久覆盖、PDF文字层不含选中内容。人工核对漏检/不支持项，不把启发式分数当安全保证。
8. 重试只处理已保存的授权Evidence，不重新抓未知网址。异常留下错误码/原件，用户明确取消被重启打断的processing记录后再重试；当前没有可靠异步队列或自动恢复执行器。旧规则保留、不同规则版本冲突人工处理。
9. 手机配置真实可达的API地址，安装调试APK后执行冷启动、离线Demo、ContentResolver分享、多文件、撤销权限、取消上传、过期版本与连续分享矩阵。当前本机无连接设备；这一步尚未完成。

独立验证入口：server下pytest -q -p no:cacheprovider；mobile下npm test及npm exec vue-tsc -- --noEmit。scripts/test-review-mobile.mjs使用既有Edge/Playwright和Mock API，需本地Vite 5193；scripts/test-harmony-rules.mjs仅验证ArkTS源码语义，不能代替DevEco编译。

新增生产依赖：无。二维码区域检测使用OCR运行栈已有OpenCV，不解码二维码；源文件永久副本使用既有Pillow/PyMuPDF。FastAPI/Starlette的弃用警告仍存在，不影响当前测试，但后续需按独立升级变更处理。
