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
| 沙箱内启动后端并用 keyring 写系统凭据 | `CredWrite` 报 `[WinError 1312] 指定的登录会话不存在。可能已被终止。` | 沙箱进程没有可用的 Windows 登录会话，凭据管理器拒绝写入 | 后端必须提权（非沙箱）启动；提权下 `keyring.set_password` 实测可用（写后及时删测试凭据） |
| Edge headless 截图失败 / 无产物 | `msedge --headless=new --screenshot=...` 返回但没生成 PNG | 本机已有 Edge 在运行，headless 复用同 profile 冲突退出（exit 13） | 截图必须带独立 `--user-data-dir=<临时目录>`；用 `Start-Process ... -Wait -PassThru` 后检查退出码与产物，不要吞 stderr |
| see.sh 在 PowerShell 直接执行无输出 | `& ...\see\scripts\see.sh image.png` 返回 0 但什么都没发生 | see.sh 是 bash 脚本，PowerShell `&` 不会执行它 | 直接用 Python 跑 `parse_media.py`（`.venv\Scripts\python.exe ...\parse_media.py <图> --task "..."`），读 stdout 的 `output_path=` 指向的 Markdown |
| PowerShell heredoc 管道执行 python 偶发解析错误 | `@'...'@ \| .venv\Scripts\python.exe -` 报「The module '.venv' could not be loaded」 | heredoc 内容含特殊字符时 PowerShell 解析管道语句异常 | 改为 `$script = @'...'@; $script \| & ".venv\Scripts\python.exe" -`，并显式设置工作目录 |

## 2. 网络与数据源

- 系统代理配置为 `127.0.0.1:10808` 但代理未运行：AKShare provider 内设置 `NO_PROXY=*` 且 `requests.Session.trust_env = False` 绕过。
- 数据源可用性（本机实测）：腾讯 `web.ifzq.gtimg.cn` 可用；东方财富被重置；新浪 hq 返回 403；Baostock 端口 10030 被拦截。
- github.com 的 HTTPS 被拦截：push/clone 走 SSH（`ssh.github.com:443`）。具体做法：`ssh-keygen -t ed25519` 生成密钥 → `gh ssh-key add <pub> --title <名称>` 注册到账号 → 配置 URL 改写 `git config url."ssh://git@ssh.github.com:443/".insteadOf "https://github.com/"`，之后 `git push` 自动走 SSH 443。
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
- **类内方法名遮蔽内置类型**：Python 类里定义 `def list(...)` 方法后，类体内**后续方法**的注解 `list | None` 会把 `list` 解析成该类方法（function）而非内置类型，报 `TypeError: unsupported operand type(s) for |: 'function' and 'NoneType'`（函数定义时注解在类体命名空间求值）。解决办法：避免用内置名做方法名（如 `list_jobs`，对齐项目 `list_providers` 风格）；或文件头加 `from __future__ import annotations` 延迟注解求值。
- **数据库迁移「已是最新结构」判定不完整**：`_migrate_jobs_table` 最初只检查 `model_id` + `cancelled_at` 列存在就跳过重建，但 M1 迁移过的旧库这两个列都在、`project_id` 仍是 `NOT NULL`，导致 `jobs.project_id=NULL` 插入报外键/非空错误。判定最新结构必须同时检查 `PRAGMA table_info(jobs)` 里 `project_id` 的 `notnull == 0`，否则旧库永远不会被重建。
- **测试数据插 job 引用不存在的 project_id 报 FOREIGN KEY**：`jobs.project_id` 有外键；脚本插入 `asset_completion` 类 job 时用了编造的 `proj_demo`，报 `IntegrityError: FOREIGN KEY constraint failed`（前几条 project_id=None 的反而成功）。插入测试数据前先查库里真实项目 id；无项目任务用 `None`。
- **插入 queued 测试 job 会被运行中的 worker 真实执行**：开发后端 worker 线程会扫描并领取 queued 任务，截图测试插入的 queued job 会因无效 provider 被真实执行成 failed（不产生费用，但状态会变）。截图数据优先用 `running/failed/completed` 等不依赖执行的状态。
- **新列索引放在 schema.sql 会导致旧库 init_db 失败**：给 `versions` 表加 `is_current` 等新列后，若把 `CREATE INDEX ... WHERE is_current = 1` 写在 schema.sql，`init_db` 的 `executescript(schema)` 在旧库上会先执行索引语句（此时旧表还没加列）报 `no such column`。依赖新列的索引必须移到 `_apply_safe_migrations` 的 ALTER 加列之后创建（`CREATE UNIQUE INDEX IF NOT EXISTS`），schema.sql 只保留不依赖新列的索引。

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
- **PowerShell 命令里的中文字面量可能编码不一致**：脚本参数中的中文常量与 API 返回（UTF-8 解析）比较会得到 False（如 `$x.name -eq '中文'`），属脚本传输编码问题，不是数据问题；验证中文数据用 Python 查库或「解析值对解析值」比较。
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

## 9. Tauri / Rust（AI Drama IDE）

- **系统没有 MSVC Build Tools 时 rustup 默认装 msvc 工具链无法链接**：本机无 VS Build Tools，但有 MinGW（`C:\Qt\Tools\mingw1310_64`）。解决办法：`rustup toolchain install stable-x86_64-pc-windows-gnu --profile minimal` 后 `rustup default stable-x86_64-pc-windows-gnu`；编译/运行前把 MinGW bin 加到 PATH。
- **MinGW windres 无法处理含空格的路径**：项目位于 `G:\Vibe Coding\AICV`，tauri-winres 调 windres 编译资源时 `cc1.exe: fatal error: ...: No such file or directory` / `windres: preprocessing failed`。根治办法是建一个无空格的 junction 路径再编译（已建 `C:\Users\Administrator\ai-drama-ide` → `G:\Vibe Coding\AICV`）；用 `scripts\tauri-dev.ps1` 一键启动，或先 `New-Item -ItemType Junction` 再 cd 到 junction 路径执行。**不要**尝试从含空格路径直接 cargo build。
- **GNU ld 无法处理 rustc 为 cdylib 生成的 `-exclude-symbols` 指令**：Tauri 模板默认 `crate-type = ["staticlib", "cdylib", "rlib"]`，纯桌面构建 cdylib（DLL）时 ld 报大量 `corrupt .drectve` / `unrecognized` 警告并链接失败。解决办法：去掉 `cdylib`，只保留 `["staticlib", "rlib"]`（移动端才需要 cdylib）。
- **tauri init 新版本不支持 `--identifier` 参数**：传该参数会报 `unexpected argument`；用其余参数初始化后，在 `tauri.conf.json` 里手动改 `identifier`。
- **cargo 进度输出走 stderr**：PowerShell 里 `cargo build 2>&1` 会把进度当 NativeCommandError 导致退出码为 1，即使编译成功；验证以产物为准（如 `target\debug\app.exe` 是否存在），或设置 `$ErrorActionPreference = 'Continue'`。
- **沙箱/CI 环境看不到 Tauri 窗口**：与第 1 节同理，GUI 进程在独立桌面运行；需提权（非沙箱）启动 `npm run tauri dev`，窗口才会出现在用户桌面。
- **沙箱中 `.git` 目录只读，git 写操作必须提权**：`git add/commit/push` 报 `fatal: Unable to create '.../.git/index.lock': Permission denied`，且目录里没有任何残留锁文件。原因：沙箱权限配置把 `.git` 设成只读，工作区其余部分可写。探测方法：在 `.git` 目录试建文件（`New-Item`），失败即需提权；之后所有 git 写命令都走提权（非沙箱）执行。
- **`tauri dev` 不启动后端，Vite 代理报 `ECONNREFUSED 127.0.0.1:8000`**：`scripts\tauri-dev.ps1` 只跑 `npm run tauri dev`（vite + cargo），FastAPI 后端必须单独启动。后端未起时页面请求 `/api/projects` 等全部走 Vite 代理失败（日志 `http proxy error: /api/projects` + `connect ECONNREFUSED`）。正确顺序：先提权启动后端 `apps\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`（工作目录 `apps\backend`，提权是因为 keyring 需要登录会话），再启动 tauri dev；若后端起晚了，刷新页面即可（SPA 的初始数据只在挂载时拉一次）。纯前端改动由 Vite HMR 热更新，无需重启 Tauri。
- **`Start-Process -ArgumentList` 传含空格脚本路径被截断**：`Start-Process powershell -ArgumentList "-NoProfile -File G:\Vibe Coding\AICV\scripts\tauri-dev.ps1"` 报「处理 -File "G:\Vibe" 失败，因为该文件不具有 '.ps1' 扩展名」。原因：ArgumentList 按空格拆分。解决办法：整个参数行写成带内嵌引号的单个字符串：`-ArgumentList '-NoProfile -ExecutionPolicy Bypass -File "G:\Vibe Coding\AICV\scripts\tauri-dev.ps1"'`。另注意：`Start-Process` 带 `-RedirectStandardOutput/-RedirectStandardError` 启动常驻进程时，启动命令自身的后续输出可能被吞，状态要另开命令查日志/进程确认。
- **阿里云百炼国内站 / 国际站是不同 endpoint，key 不通用且能力检测会互相误判**：国内站 base_url 为 `https://dashscope.aliyuncs.com`（`bailian` 预设），国际站为 `https://dashscope-intl.aliyuncs.com`（`bailian-intl` 预设）；用国内站 key 打国际 endpoint（或反之）做模型发现/能力检测会被误判为「模型不存在/不支持」。两者必须拆成独立 Provider 预设，各自带自己的 base_url，不要把 key 混用。
- **SQL WHERE 占位符与参数个数不匹配**：`list_episodes` 曾漏掉 `project_id = ?` 条件，但 params 仍传入 project_id（+ 可选 novel_id），SQLite 报 `ProgrammingError: Incorrect number of bindings supplied. The current statement uses 1, and there are 2 supplied.`，接口变 500「服务器内部错误」。写 SQL 时先数一遍 `?` 占位符，确保与 params 列表一一对应；测试必须覆盖「带可选过滤参数」的列表查询路径（前端保存后刷新列表正是这条路径），不能只测 detail 单条查询。
- **uvicorn 无 `--reload` 时新增路由不生效**：后端启动命令没带 `--reload`，新增 `assets` 路由后接口一直 404。排查思路：先 curl 直连后端确认是「后端没加载路由」还是「Vite 代理问题」；开发期新增路由后必须重启后端（或启动时带 `--reload`）。
- **旧项目 Bible JSON 缺新字段（asset_id 为空）**：Phase 8 给 Bible 实体加 `asset_id` 后，老项目（存量 stories 表 JSON）里该字段为空，前端资产列表/标题徽标全部空白。修复：`list_assets` 读取时检测空 asset_id → 先 `save_bible` 落库分配稳定 ID（复用 `asset_type_slug_seq`）再返回；不要在 UI 层手补 ID。
- **PowerShell `$pid` 是保留变量**：`foreach ($pid in $listeners)` 直接报 `Cannot overwrite variable PID`，导致 Stop-Process 循环没执行、后端没重启。遍历进程号时用 `$procId` 等自定义变量名。
- **starlette TestClient.delete 不支持 `json=` 参数**：DELETE 带 body 的接口测试用 `client.delete(url, json=...)` 会抛 `TypeError`；改用 `client.request("DELETE", url, json=...)`。
- **依赖 projectId 的数据加载写进了挂载 effect**：资产页把 `getAssetSpecs` 放在 `active` effect（挂载时跑一次）里，但此时项目还没选中，导致选中项目后规格选项一直为空（比例下拉只有「默认」、画风下拉空白）。凡「选中项目后才需要的数据」（如资产规格、列表）必须放在依赖 `projectId` 的 effect 里，与刷新列表同批触发。
- **PyInstaller 打包 FastAPI 后端**：`uvicorn.run("app.main:app")` 字符串导入不会让 PyInstaller 收集 `app` 包 → exe 启动即崩溃且无日志；必须 `from app.main import app` 直接传 app 对象。`schema.sql` / `vendor_models.json` 等运行时读取的数据文件默认不收，要 `--add-data`（源路径用绝对路径，否则会被解析到 `--specpath` 目录下报「Unable to find」）。
- **Tauri sidecar 双后缀**：运行时（shell 插件/std spawn 前）按编译 target triple（GNU）找 `name-x86_64-pc-windows-gnu.exe`，而 Tauri bundler 打包时按 Windows 默认 triple 找 `name-x86_64-pc-windows-msvc.exe` 并安装为无后缀名。同一后端二进制必须保留两个后缀名的文件（`build-backend.ps1` 已处理），缺 msvc 后缀会 `failed to bundle project: resource path ... doesn't exist`。
- **MinGW GNU 构建下 WebView2Loader.dll 不进安装包**：NSIS bundler 在 GNU 工具链下不会自动收集 `WebView2Loader.dll`，安装后启动报「找不到 WebView2Loader.dll」。必须在 `tauri.conf.json` 的 `bundle.resources` 显式加 `"target/release/WebView2Loader.dll": "WebView2Loader.dll"`。
- **x64 应用找不到 WebView2 运行时**：本机 WebView2 只注册在 `WOW6432Node`（32 位视图），x64 Tauri app 初始化失败报「找不到 WebView2」。对策：`webviewInstallMode: { "type": "embedBootstrapper" }`，安装器检测缺失时联网静默补装（+1.8MB）。
- **退出时清理 sidecar 进程树**：PyInstaller onefile 有父（bootloader）+ 子（解压运行）两个进程。清理顺序必须先 `taskkill /PID <pid> /T /F`（父还活着才能枚举子进程）再 `child.kill()`；先杀父会让 `/T` 失效、子进程残留。
- **NSIS 静默安装/卸载验证**：`setup.exe /S` 静默安装到 `%LOCALAPPDATA%\AI Drama IDE Lite`（perUser 模式），`uninstall.exe /S` 静默卸载；卸载不会删 `data/` 用户数据（符合预期）。验证安装包用「卸载→重装→启动→taskkill 关闭」链路。

## 10. 视频生成与多 Provider 协议（Phase 14）

- **智谱 CogVideoX 时长只支持 5/10，传 15 返回 HTTP 400**：前端统一时长 5/10/15，但智谱视频 `duration` 仅 5、10，传 15 直接被 400。修复：`ZhipuVideoAdapter.submit` 把 `duration > 10` 收敛为 10（Sora 类似，映射 5→4、10→8、15→12）。新增厂商视频 Adapter 时先核对时长枚举，不要透传通用时长。
- **Sora / OpenRouter 视频结果 URL 需要鉴权下载**：轮询完成后 `content` 端点（`/videos/{id}/content`）要求 Authorization，而 `ImageResultService._materialize` 原本只做无鉴权 GET。修复：`GenerationResult` 增加 `download_headers`，Adapter 在 poll 完成时把 `Authorization: Bearer ...` 放进结果，`_materialize` 下载时透传；`_result_payload` 不持久化 headers，避免 key 落库。
- **视频模型不在 OpenAI 兼容 `/models` 列表**：DashScope 视频走 `video-synthesis`、智谱走 `videos/generations`、SiliconFlow 走 `video/submit`、OpenRouter/Sora 走 `videos`，`/models` 只返回 LLM 和部分图片模型。只做 discover 会永远拉不到视频模型。修复：`discover-models` 在 `/models` 结果上合并 `vendor_models.json` 内置目录，且 `upsert_discovered` 对内建模型优先用其准确 `type`/`capabilities`，不按名称猜。
- **已有 preset Provider 的 protocol 不自动跟随新预设**：新增 `sora` / `openrouter_video` / `zhipu_video` / `siliconflow_video` 协议后，库里旧 provider 仍是 `openai_compat`，导致视频模型存在却走错 Adapter。修复：`database.py` 启动迁移 `UPDATE providers SET protocol = preset.protocol WHERE preset_key = ? AND protocol = 'openai_compat'`，只在默认值时才迁移，不覆盖用户手改的协议。
- **阿里云百炼 Wan 图生视频 REST 字段是 `input.img_url`，不是 `input.media`**：旧实现用 `input.media[type=first_frame]` 会请求失败。以官方最新 `image-to-video guide` 为准：`input.prompt + input.img_url`（或音频时再加 `audio_url`），轮询 `GET /api/v1/tasks/{id}` 取 `output.video_url`。
- **分镜参考图在 dev 模式永远不加载**：`StoryboardPage` 的参考图 effect 曾写 `if (!projectId || !apiBase) return`，而 Tauri dev 下 `getApiBase()` 返回空字符串，导致资产参考图列表永远为空、显示「暂无可用的资产图片参考图」。修复：去掉 `!apiBase`，改为 `if (!active || !projectId) return`，图片 src 用相对路径走 Vite 代理。
- **切资产页生成图片后回分镜页参考图不刷新**：参考图 effect 只依赖 `projectId`，资产页生成新图片后切回分镜页不会重新加载。修复：依赖加入 `active`，每次进入分镜页重新拉取有当前图片版本的资产。
- **qwen-audio-*-asr 被误判为 TTS 音频模型**：阿里云百炼的 `qwen-audio-3.0-asr-flash` 是语音识别模型，不是语音合成；旧规则把 `qwen-audio` 笼统归为 audio，导致配音 Job 自动选中它并调用 `/multimodal-generation/generation` 返回 HTTP 400。修复：vendor type rules 去掉 `qwen-audio` 泛匹配；`_backfill_model_capabilities` 启动时按 `classify_model` 同时刷新 auto 模型的 `model_type` 和 capabilities，旧库里已经误判的 ASR 模型会自动变成 `llm`。
- **视频原生音效不应默认启用**：智谱 / OpenRouter 视频模型原生生成的音效效果不稳定，且会和后续台词配音混叠。产品已改为所有视频先生成无声版本，音效 / BGM 由用户导入本地音频，台词统一用 TTS 配音；后端 `VideoGenerateRequest` 不再暴露 `with_audio`，前端也不根据 `video_audio` 能力自动开启原生音效。
- **当前配音没有逐句时间轴和口型对齐**：`AudioDubbingService` 只把台词拆成多段 TTS 后按顺序 concat，再与视频从 0 秒开始混音；没有对齐到具体镜头内的时间点，也没有口型 / lip-sync。后续需要真正对口型时，必须增加台词时间戳、ASR/音素对齐或视频生成模型的语音驱动能力，不能把当前配音误认为已经对齐。
- **`extract_json` 只识别对象，不识别 JSON 数组**：`extract_json` 之前只查找 `{...}`，导致“台词归属”等需要返回 JSON 数组的接口即使 LLM 输出正确，也会解析失败并回退成整段台词一行。修复：`extract_json` 同时识别 `{...}` 和 `[...]`，选择最先出现的有效边界。
- **不要把“混音”和“封装视频”放在同一条 FFmpeg 命令里**：旧 `mix_audio_video` 同时完成多路音频混音、AAC 编码和视频封装，无法单独复用音频母带。拆分声音管线时，先 `mix_audio_to_master` 输出 WAV 母带，再用 `compose_video_with_audio` 以 `-c:v copy` 将无声视频与母带封装，避免视频被重复编码，也方便以后单独重混或替换母带。
- **声音子任务如果直接进入 Job Queue，会被 worker 二次领取**：当前配音仍是单个前端可见的 `dubbing` 父 Job。拆分 `audio_separation` / `dialogue_planning` / `tts_generation` / `audio_mixing` / `media_compose` 时，子任务在父 Job 内部同步执行并立即标记终态，不留在 `queued` 状态，避免 worker 下一轮重复执行或产生重复 TTS 费用。
- **Lip Sync 的 PassThrough 只封装音频，不替换嘴型**：`PassThroughLipSyncAdapter` 复用 `compose_video_with_audio`，输出 `shot_video_lip_synced` 版本但画面不变。它用于验证「Video + Final Audio → Synced Video」独立 Job 流程，不能被当作真实对口型结果。接真实实现（LatentSync / Sync.so）时直接替换 Adapter，不改 Job 结构。
- **Lip Sync 输入必须用无声视频 + 最终音频母带，而不是有声视频**：配音流程已约定视频先生成无声版本、音频由混音输出 WAV 母带。Lip Sync 若误用 `shot_video_voiced` 作输入，会重复封装音频或产生双重音轨；`LipSyncService.create_job` 校验的是 `shot_video` 当前版本 + `audio_mix_sessions` 最近 completed 的 `output_audio_path`。
- **M3 时间轴不依赖 LLM / 字符数估算**：`TimelineService.probe_audio_duration` 用 FFmpeg 探测真实时长；TTS Provider 返回 timestamps 时才用字符/词级 alignment，否则一律 `audio_duration_only`。任何「每句话 X 秒」「按字符数估算」的实现都不允许出现。
