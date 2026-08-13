# QuantNova 开发踩坑记录

> 本文记录 QuantNova（C++ Qt 客户端 + FastAPI Python 引擎 + SQLite）开发过程中遇到的环境、网络、构建、运行时问题与解决办法，按类别整理，便于后续开发快速排查。
>
> **维护约定：开发中遇到任何新的坑，请及时按「现象 / 原因 / 解决办法」格式补充到对应分类，不要遗漏。**

## 0. 环境与工具链基准

- Python 3.12.10（`.venv`）：numpy 2.5.2、pandas 3.0.5、scipy 1.18.0、fastapi 0.141.1、uvicorn、akshare 1.18.84、pytest、pylint、black、cmake 4.4.2、ninja
- Qt 6.8.3：`C:\Qt\6.8.3\mingw_64`（含 Charts）；MinGW 13.1：`C:\Qt\Tools\mingw1310_64`
- 后端启动：`.venv\Scripts\python -m uvicorn api.app:app --host 127.0.0.1 --port 8000`
- 客户端编译前需设置 PATH：

  ```powershell
  $env:PATH = "C:\Qt\6.8.3\mingw_64\bin;C:\Qt\Tools\mingw1310_64\bin;E:\FintechProject\.venv\Scripts;$env:PATH"
  .venv\Scripts\cmake.exe --build cpp_client\build
  ```

## 1. 命令执行环境 / 沙箱（最隐蔽、最易误判）

| 坑 | 现象 | 原因 | 解决办法 |
| --- | --- | --- | --- |
| `Start-Process` 加 `-RedirectStandardOutput/-RedirectStandardError` 启动常驻程序 | 命令一直不返回，看起来像死循环 | 重定向管道要等子进程退出才关闭，而客户端/后端是常驻进程 | 启动 GUI 或后台服务不要加重定向；需要日志就让程序自己写文件 |
| 沙箱内启动 GUI 客户端 | 进程在跑，但用户看不到任何窗口 | 命令执行环境运行在独立桌面（`CodexSandboxDesktop-xxx`），窗口落在不可见桌面 | 用提权（非沙箱）方式启动客户端，窗口才会出现在用户桌面 |
| 沙箱内启动后端 | 在线拉取全部失败，提示「所有行情数据源暂时不可用」 | 沙箱禁止外网访问 | 后端必须用非沙箱方式启动，才能访问腾讯等数据源 |
| 沙箱内直接访问外网 | 腾讯/新浪等全部连接失败 | 沙箱网络限制 | 排查网络问题先做对比测试：沙箱失败 + 提权成功 = 环境限制，不是数据源故障 |
| PowerShell 输出被吞 | 命令执行成功但没有输出 | 执行环境吞输出 | 输出重定向到日志文件，或分两次命令分别检查状态 |
| pytest 临时目录清理报 `PermissionError: [WinError 5]`（`pytest-of-Administrator`） | 测试本身全过，teardown 阶段清理系统 Temp 失败 | 系统 Temp 目录权限/占用问题（Windows 沙箱） | 运行时指定项目内临时目录：`pytest --basetemp=E:\FintechProject\.pytest_tmp -p no:cacheprovider` |

## 2. 网络与数据源

- 系统代理配置为 `127.0.0.1:10808` 但代理未运行：AKShare provider 内设置 `NO_PROXY=*` 且 `requests.Session.trust_env = False` 绕过。
- 数据源可用性（本机实测）：腾讯 `web.ifzq.gtimg.cn` 可用；东方财富被重置；新浪 hq 返回 403；Baostock 端口 10030 被拦截。
- github.com 的 HTTPS 被拦截：push/clone 走 SSH（`ssh.github.com:443`，配置在 `~/.ssh/config`）。
- `/data/fetch` 返回 422 的两种含义要区分：Pydantic 参数校验失败（请求体错误） vs 业务层「所有行情数据源暂时不可用」（网络/数据源问题，非用户操作导致）。后者是中文 detail，客户端会展示。

## 3. 后端与数据

- 保存持仓 404「用户不存在」：早期数据库 `users` 表为空、客户端写死 user_id=1；登录注册上线后解决（注册即建用户、取真实 user_id）。
- 保存持仓 422「资产不存在」：先在线拉取/导入行情入库（`save_prices` 会自动创建资产），再保存持仓。
- 日期连续性校验：默认最大缺口 15 天（财报/节假日）；历史数据如 600519 存在 1–8 月断档，分析路径已放宽到 `max_gap_days=400`，否则会误拒。
- SQLite 只存数据、不存 BLOB；报告存文件路径 + 元数据（`reports` 表）。
- 数据库迁移必须幂等：`ALTER TABLE ... ADD COLUMN` / `CREATE UNIQUE INDEX IF NOT EXISTS` 包在 try/except 里（参考 `storage.py` 的 `_migrate_*` 模式），兼容旧库。
- 密码禁止明文存储：PBKDF2-SHA256 加盐哈希；会话 token 数据库只存 SHA-256 哈希，可服务端注销。
- 券商导出的持仓 CSV **没有统一格式**：编码常见 GBK/UTF-8（带 BOM），列名五花八门（证券代码/股票代码/代码、持仓数量/证券数量/数量、成本价/参考成本价…）。解析必须做编码探测（utf-8-sig → gbk → gb18030）+ 列名模糊匹配（归一化后“包含匹配 + 最长别名优先”，并排除“盈亏比例/冻结数量”这类易误配列）；禁止假设固定列名或 UTF-8。
- CSV 文件内容传输：客户端用 Base64 包一层 JSON 上传（保留原始字节），由后端做编码探测，避免 Qt 端按本地编码读 GBK 文件导致乱码；文件大小限制 5MB。
- **阿里云百炼文生图**：OpenAI 兼容的 `compatible-mode/v1/images/generations` 对该账号返回 404；正确路径是 DashScope 原生异步接口 `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis`（header 必须带 `X-DashScope-Async: enable`），`parameters.size` 用 `1024*1024`（星号），创建任务后轮询 `GET /api/v1/tasks/{task_id}` 直到 `SUCCEEDED` 再取 `output.results[0].url`；实测 `qwen-image-plus` 可用。
- **imagegen skill 换模型**：其 CLI 校验 `--model` 必须是 `gpt-image-*`，无法直接换 qwen/wanx 等模型；换第三方模型时直接用 openai SDK 指定 `base_url`（如百炼兼容端点）或按官方端点写一次性调用，不要改 skill 脚本。
- **OpenAI key 无额度**：`429 insufficient_quota / credit_balance_exhausted` 表示账户余额为 0，换 key/充值前无法生成；OpenAI 系 gpt-image-1.5/1 与 gpt-image-2 共用同一账户额度，换模型无济于事。
- **PyInstaller 打包缺数据文件**：`storage.py` 用 `Path(__file__).with_name("schema.sql")` 读建表 SQL，PyInstaller 默认只收 `.py`，打包后首次建库报 `FileNotFoundError: ...\_MEIxxxx\python_engine\data\schema.sql`（接口 500 且响应体为空）。修复：在 `quantnova-server.spec` 的 `datas` 中加入 `('python_engine/data/schema.sql', 'python_engine/data')`；以后新增运行时读取的数据文件都要同步进 spec。

## 4. 客户端 / Qt

- Qt 6.8 使用**全局 `QtCharts` 命名空间**，不是 `QtCharts::`。
- 重新编译前必须先结束 `quantnova_client` 进程（Windows 文件锁），否则链接报 `Permission denied`。
- 编译链接需要正确 PATH（Qt bin + MinGW bin + venv Scripts），且客户端运行时也需要 Qt bin 在 PATH 中。
- 开发版客户端**不带 Qt bin PATH 启动会几秒后静默退出**（缺 DLL）；用 `Start-Process` 前先 `$env:PATH = "C:\Qt\6.8.3\mingw_64\bin;..."`，打包版（windeployqt 已复制 DLL）不受影响。
- `cmake` 不在系统 PATH 时用 venv 里自带的：`.venv\Scripts\cmake.exe --build cpp_client\build --parallel`（venv 内含 cmake 4.4.2 + ninja）。
- **验证窗口图标**：`CopyFromScreen` 截屏会截到遮挡窗口（当前置前台的不是目标窗口）；用 `PrintWindow(hWnd, hdc, 0)` P/Invoke 直接捕获指定窗口内容，无需打断用户。
- **see.sh 静默失败排查**：它 `exec python3 ...`，Windows 上 `python3` 常指向 WindowsApps 假别名导致无输出退出；在 `.venv\Scripts\` 放一个复制的 `python3.exe` 垫片，并在 bash 里 `export PATH="/e/FintechProject/.venv/Scripts:$PATH"` 即可。
- **Qt 图标集成**：窗口/任务栏图标用 `app.setWindowIcon(QIcon(":/..." ))` + `.qrc`（需 `CMAKE_AUTORCC ON`）；exe 文件图标用 `.rc` 文件（`IDI_ICON1 ICON DISCARDABLE "..\\icons\\x.ico"`）加入 `add_executable`，CMake 需 `enable_language(RC)`；图标资源放 `cpp_client/src/resources/icons/`。
- **MinGW Qt 客户端默认是控制台子系统**：`add_executable` 不写 `WIN32` 时，exe 被链接成 `Windows CUI`，双击启动会弹出黑色终端（被 start.bat 的 cmd 窗口掩盖过，改成快捷方式直启客户端后暴露）。修复：`add_executable(quantnova_client WIN32 ...)` 并链接 `Qt6::EntryPointPrivate`（Qt 6.8 mingw 只有 Private 变体，没有公开的 `Qt6::EntryPoint`）。验证：`objdump -x quantnova_client.exe | Select-String Subsystem` 应为 `Windows GUI`（00000002）。
- **Qt 资源（qrc）必须放在 exe 目标而不是静态库**：qrc 编进静态库时链接器可能丢弃该目标文件导致资源未注册，运行时 `:/...` 资源全部加载失败（如登录框 logo 空白、窗口图标回退到系统默认）。把 `.qrc` 加入 `add_executable(...)` 即可。
- **全局深色 QSS 与局部浅色对话框混用**：浅色对话框必须显式设置所有控件的文字颜色，否则会继承全局主题的白色文字（输入框文字、placeholder、标签都会“隐形”）。登录框已在样式表里显式设置 `QLabel`、`QLineEdit`、`QLineEdit::placeholder`、`QPushButton` 的颜色；以后新增浅色界面按此清单检查。
- GoogleTest 克隆在 `cpp_client/third_party/googletest/`，被 gitignore；缺失时通过 SSH 重新获取。
- 在 exe 里搜字符串：`QStringLiteral` 编译为 **UTF-16**，用 ASCII 文本方式搜不到；需转成 UTF-16LE 字节再搜。
- 客户端启动无窗口排查：进程活着但 `MainWindowHandle=0`，优先怀疑启动环境桌面问题（见第 1 节）；需要定位卡点可在启动链路上加 `qDebug` 追踪（main/Application/MainWindow/LoginDialog），日志落到文件后分析。
- 登录状态：token 存本地 QSettings（单机桌面可接受），登出时清除并调 `/auth/logout` 注销会话。
- 客户端维护“活跃股票集合”时，拉取/导入成功后**追加去重**（`addSymbol`），不要整体替换 `lastSymbols_`，否则新股票会把上一只股票“吞掉”；加载持仓时与已有集合做并集。
- 多资产分析时，日期范围不同的序列合并会产生合法的对齐空值：校验必须**按单只资产各自的有效交易日**进行（`dropna` 后校验），不能对合并宽表直接校验“缺失值”，否则导入第二只股票后分析会误报「存在缺失值」。
- Windows 批处理文件（`.bat`）必须用 **CRLF 换行**：用补丁工具创建时默认是 LF，cmd 解析会错乱（报“not recognized”类错误）；写完需转成 CRLF（无 BOM）。
- 用 `Start-Process`/`start` 从命令行启动 GUI 程序时，子进程会继承管道句柄导致命令一直不返回——脚本本身没问题，属测试环境的假象；从资源管理器双击运行不受影响。
- 客户端处理 HTTP 错误时，**有状态码（≥400）且服务端返回了 `detail` 时优先直接展示该中文详情**，不要先拼接“网络请求失败”之类的网络层文案——否则业务错误（参数、卖空、数据源不可用）会被误报成网络问题；网络提示只用于真正无 HTTP 响应的连接/超时类错误。
- see 技能在 Windows 上的坑：配置文件 `%APPDATA%\see\config.env` 权限损坏会导致 onboard/see 全部 Permission denied（用 `icacls <文件> /reset` 修复）；沙箱禁外网会让云识别（bailian 等）报 WinError 10013，需提权运行；`python3` 若指向 WindowsApps 假别名会被拦截，可在 PATH 前置一个复制自 `C:\...\Python312\python.exe` 的 `python3.exe` 垫片。
- 主模型不支持图片时，聊天附件会被平台在进入对话前丢弃：see 等读图技能**拿不到聊天里的图片**，只能读本地文件路径；截图若还在剪贴板，可先用 `[System.Windows.Forms.Clipboard]::GetImage()` 存成 PNG 再喂给技能。

## 5. 编码与格式

- 源码为 UTF-8（无 BOM）；PowerShell 默认编码读取会显示乱码（GBK 误读），读文件用 `Get-Content -Encoding UTF8`。
- 打补丁时中文上下文必须与文件真实内容（UTF-8）一致，不能粘贴乱码显示内容，否则匹配失败。
- 本机 black 缓存损坏会挂起：运行前先设置 `$env:BLACK_CACHE_DIR = "$env:TEMP\black_cache_qn"`。
- API 返回的 UTF-8 中文在 PowerShell 控制台显示成乱码（如 `äº”ç²®æ¶²`）是**控制台编码误读**，不是数据问题；用 `Invoke-RestMethod | ConvertTo-Json` 或写文件验证时注意区分。
- Python 规范：Black 格式化 + Pylint 检查（`pylint -E api python_engine` 应为 0 错误）+ pytest；提交遵循 Conventional Commits（feat:/fix:/refactor:/docs:）。
- PowerShell 5.1 字符串插值陷阱：`"$var?name=foo"` 会把 `$var?` 解析成特殊变量，结果变成 `=foo`（URL 里的 `?` 后内容全部丢失）。带查询参数的 URL 拼接必须用 `$var + '?name=foo'` 或 `${var}?name=foo`，否则 curl/Invoke-RestMethod 拿到畸形 URL（curl 报 `URL rejected: Bad hostname`）。
- **PowerShell 5.1 发中文 JSON body 变 `?`**：`Invoke-RestMethod -Method Patch -Body $jsonString` 默认按 ASCII 编码发送，所有中文变成问号（GitHub 仓库 description、Release 说明都中过招）。必须先把 body 转成 UTF-8 字节数组再发：`$bytes = [Text.Encoding]::UTF8.GetBytes($json); Invoke-RestMethod ... -ContentType 'application/json; charset=utf-8' -Body $bytes`；Topics 等纯英文字段不受影响。

## 6. 端口与进程管理

- 8000 端口可能有残留 uvicorn 子进程（子进程继承 socket），清理方式：

  ```powershell
  netstat -ano | Select-String ':8000.*LISTENING'
  # 找到 PID 后逐个结束（可能需要提权）
  Stop-Process -Id <PID> -Force
  ```

- `Stop-Process` 报 Access denied 时用提权方式执行。

## 7. 快速启动清单（避免踩坑）

1. 结束旧进程：`quantnova_client` 进程、8000 端口占用。
2. **非沙箱（提权）启动后端**，否则外网不可达、拉取必失败。
3. **非沙箱（提权）启动客户端**，否则窗口落在不可见桌面。
4. 客户端登录后：在线拉取行情 → 保存持仓 → 重启客户端自动登录并恢复持仓。

## 8. 打包（PyInstaller）

- 后端打包入口：`scripts/server_main.py`（`create_app()` + `uvicorn.run`，支持 `--host/--port` 参数）；构建命令：`scripts\build_server.bat`（即 `pyinstaller quantnova-server.spec --noconfirm --clean`）。
- 产物 `dist\quantnova-server.exe` 约 124MB，onefile 首次启动约 5–10 秒（解压到 `%TEMP%\_MEIxxxx`）。
- 打包后数据目录跟随 exe：`config.py` 在 `sys.frozen` 时把 `PROJECT_ROOT` 指向 exe 所在目录，`data\quantnova.db`、`output\`、`.env` 都在 exe 旁边，便携可迁移。
- 验证打包是否完整，最小冒烟集：`/health` → 注册/登录（验证建库）→ `/simulation/monte-carlo`（验证 numpy/scipy）→ `/data/connectivity`（验证 akshare 网络层，结果取决于网络/沙箱）。
- **onefile 启动竞态（双实例）**：后端 exe 解压约需 5–10 秒；客户端启动后立即健康检查若失败会触发 `ensureBackend`，与 `start.bat` 各自拉起一个后端 → 8000 端口争抢、出现 2 组 quantnova-server 进程。修复：客户端在启动新后端前先带重试探测 `127.0.0.1:8000`（最长约 6 秒），已就绪则跳过；`start_release.bat` 也先等 `/health` 就绪再拉起客户端。
- **PyInstaller windowed（console=False）版 stderr 为 None**：无控制台模式下 `sys.stderr/sys.stdout` 为 None，uvicorn/logging 的 StreamHandler 写日志直接抛异常 → 启动失败（健康检查不通、进程残留）。修复：frozen 模式下把 stdout/stderr 重定向到 `data\server.log`（`_redirect_stdio_in_frozen_mode`），spec 设 `disable_windowed_traceback=True` 避免崩溃弹窗。
- **Compress-Archive 丢顶层目录**：`Compress-Archive -Path "$dir\*"` 会把目录本身丢掉，zip 里文件散落在根部；要保留顶层文件夹必须用 `-Path $dir`（不带 `\*`）。另外 PS 5.1 的 Compress-Archive 产物里 `ZipArchiveEntry.FullName` 用**反斜杠**（如 `QuantNova\.env`），判断条目时注意分隔符，别按惯例用 `/`。
