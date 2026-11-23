# RF-013 同一通知下两份表单的草稿复现

在仓库根目录运行。需要 Node.js 22 或以上、npm 和本机 Microsoft Edge。Playwright 仅用于此探针，安装到忽略目录。脚本自行启动本地 Vite 与无头 Edge，使用仓库自带合成模板，结束时关闭二者。

~~~powershell
npm ci --prefix mobile
npm install --prefix .runtime/form-probe --no-save --package-lock=false playwright@1.65.0
$env:NODE_PATH = (Resolve-Path .runtime/form-probe/node_modules).Path
node docs/development/records/evidence/D_20261121/check_form_reselection.cjs
~~~

基线 ce3ecd4。390×844 页面中，A、B 各有姓名、学号、申请理由。只改通知，两表共 6 项保留；派发取消事件，B 的 3 项保留。仅修改 A 的 ZIP 注释后重选两份文件，新 A 显示未核验，原件完全相同的 B 可打开但 3 项为空；再选回原 A，其 3 项也为空。PASS 表示复现这些现象。团队确认新行为并修复后应同步修改断言。原生文件选择器取消、刷新和重新登录需要分别验证。
