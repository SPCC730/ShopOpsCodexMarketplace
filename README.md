# ShopOps Codex Marketplace

公开的 ShopOps Codex 插件分发仓库。当前发布的
`shopops-onboarding 0.1.12+codex.20260908093755` 用于安全安装、更新和诊断
`ShopOps Reporter 0.5.0`，并提供经确认的项目接入和运行结果契约配置指引。

Reporter 0.4.2 于 2026-09-08 发布，开发者安装分支为
`codex/shopops-plugin-dev`。插件版本与 Reporter 版本分别管理，更新插件不会
自动升级本机 Reporter。

版本及安装包校验依据：

Reporter 0.5.0 新增结果契约 v2：代码变化自动复用已审核契约，业务口径、
映射和上报范围变化才提交新版本。现有 v1 项目需要一次迁移审核；升级不会自动迁移。
当前正式离线分发为 0.5.0。

- [插件版本](plugins/shopops-onboarding/.codex-plugin/plugin.json)
- [Reporter 分发清单](plugins/shopops-onboarding/reporter-manifest.json)
- [安装包 SHA-256](plugins/shopops-onboarding/checksums.json)

完整交互式说明书：

- 局域网：<http://192.168.10.201:5174>
- ShopOps Mac mini 本机：<http://127.0.0.1:5174>

## 开发者 5 分钟开始

### Reporter 0.4.2 更新说明

- 新增带设备签名的独立版本心跳，后台启动后立即上报实际运行版本，随后约每 30 秒更新。
- 版本同步不再依赖项目同步或业务运行；旧运行及离线队列中的版本不会覆盖当前设备版本。
- 旧服务器仅在新接口返回 `404/405` 时回退到原在线心跳；鉴权、签名及其他错误不会被回退掩盖。
- 保留 0.4.1 的指纹、契约快照与后台身份修复，八套离线包的第三方依赖不变。

管理员先部署支持设备版本心跳的后端。开发者更新本插件后，在新 Codex 任务中调用
`$shopops-update`，确认目标 **0.4.2** 并升级。确认旧后台身份后正常停止旧进程，再启动新版；
仅更新插件或安装新包不会替换已运行的旧进程。不得仅凭 PID 结束进程。
后台上报成功后，外部接入设备列表在下一次刷新时显示新版本；页面可见时约每 15 秒刷新。
无需重新配对、重新初始化项目或运行业务脚本，不修改历史结果，设备身份和离线队列保留。
连接旧后端的回退只更新在线状态，仍不能解决版本滞后。

### Reporter 0.4.1 更新说明

- 修复运行输出 JSON 变化造成项目指纹失配的问题，提供显式的 v2 输出路径声明及一次性迁移。
- 后台状态同时验证进程身份、启动时间和本机健康接口；增加单实例锁，停止时通过带凭证的本机接口退出。
- 新运行保存结果契约快照；项目配置原子写入。原项目身份、旧契约与离线队列保留。
- 八套离线包覆盖 macOS arm64、Windows x64 的 CPython 3.11–3.14，均包含 `psutil`。

管理员先部署支持 v2 指纹契约的 ShopOps 后端。开发者更新本插件后，在新 Codex 任务中
调用 `$shopops-update` 升级到当前 **0.4.2**（包含 0.4.1 修复）。插件更新本身不会升级 Reporter，也不会重启旧后台。
旧后台仅有 PID 标记时，新版将显示 `legacy_unverified`；需从原启动终端或服务管理器
确认并正常停止旧进程，再启动新版，不能仅凭 PID 结束其他程序。

升级不会自动转换旧项目的指纹。确认输出范围、暂停新增业务运行后，在原项目目录执行：

```bash
shopops-report result-contract migrate-fingerprint --output data/result.json
```

路径只是示例，必须按实际项目列出动态输出文件；多个文件重复使用 `--output`。
不允许整个 `data/`、通配符或源码路径，也不能把业务输入配置当作输出。
此命令会提交新契约并保留旧契约备份，不执行业务脚本；新版本需管理员审核。
迁移后源码、业务配置和契约规则的变化仍需更新契约。历史结果的校验状态不回填，
已有离线记录继续使用原版本。详细步骤见在线说明书的“项目指纹迁移与后台状态”。

### 1. 确认仓库可访问

本仓库是公开仓库，不需要 GitHub 协作者邀请或登录。先确认当前电脑可以访问
<https://github.com/SPCC730/ShopOpsCodexMarketplace>；如果网络无法访问 GitHub，
请向管理员索取内网镜像或离线插件包。

### 2. 添加 Marketplace 并安装插件

在 Codex CLI 中添加团队 Marketplace：

```bash
codex plugin marketplace add SPCC730/ShopOpsCodexMarketplace \
  --ref codex/shopops-plugin-dev
```

然后打开 Codex 的 **Plugins** 页面，选择 **ShopOps Internal**，安装
**ShopOps Onboarding**。安装后新建一个 Codex 任务；旧任务不会自动加载新技能。

### 3. 安装并诊断 Reporter

在新任务中发送：

```text
请使用 $shopops-onboard 安装 ShopOps Reporter。展示完整安装预览，等我确认后再安装。
```

确认安装预览中的版本后，再允许 Codex 安装。完成后发送：

```text
请使用 $shopops-doctor 只读诊断 ShopOps Reporter。
```

首次安装显示 `not_paired` 是正常状态；`healthy` 表示安装诊断正常，不保证
项目同步成功或业务脚本已完成。安装预览中的 `changed: false` 表示没有写入，
不是已经安装成功，仍需确认安装并核对实际版本。

已有 Reporter 的电脑更新时，先从上述分支更新插件，再在新任务中发送：

```text
请使用 $shopops-update 按 ShopOps 安全更新流程检查并升级 Reporter。先展示目标版本和影响范围，等我明确确认后再升级；保留设备身份、项目配置和离线队列，不重新配对、不重新上传项目，也不要运行任何业务脚本。
```

锁定离线安装当前覆盖：

- Apple Silicon macOS，CPython 3.11 及以上的 Python 3 版本；
- Windows 10/11 x64，CPython 3.11 及以上的 Python 3 版本。

当前锁定的离线安装包覆盖 CPython 3.11、3.12、3.13 和 3.14；更新的
Python 版本需要先发布对应的 wheelhouse，插件不会拿其他 ABI 的包冒充安装。

Windows 稳定命令位于
`%LOCALAPPDATA%\ShopOps\Reporter\bin\shopops-report.cmd`。Marketplace 根目录的
Python 版本只用于仓库开发测试，不是 Reporter 的运行版本约束。

本仓库不包含主项目的 `reporter/pyproject.toml`，这项源码文件检查应标为
“不适用”，而不是环境检查失败。请使用插件 `probe` 与 `install-preview`，
并核对匹配 wheel 的 `.dist-info/METADATA` 中的 `Requires-Python`（当前为
`>=3.11`）、分发清单和 SHA-256。不能仅凭 README 或仓库根目录的 Python
要求判断 Reporter 是否可安装，也不要为了缺少源码文件改成联网安装。

### 4. 配对并接入项目

管理员在 ShopOps **外部接入** 页面生成一次性配对码。开发者使用
`shopops-report enroll` 配对电脑，然后在每个独立脚本项目副本中执行一次
`shopops-report init`。管理员确认待接入 SOP 后，日常运行只需：

```bash
shopops-report run
```

日志、结构化结果和明确声明的附件会进入 ShopOps **运行中心**。完整参数、正确
结果示例、断网补传和排障方式请查看交互式说明书。

## 0.4.0 项目同步与升级验收

管理员应先确认 ShopOps 后端支持项目同步与当前设备管理，再安排客户端升级。
升级保留设备身份、项目配置和离线队列，不需要重新配对或重新上传项目；
升级流程不会自动启动后台，需检查后台状态并在明确授权后按需启动。

Reporter 后台运行时约每 60 秒独立同步已登记项目的名称、用途、可选版本和
运行方式，不依赖业务脚本先执行。旧配置不会自动补齐未声明的信息，不确定的
运行方式保留 `unknown`。启动命令、上传范围或看板变化仍需显式执行 `sync`；
结果契约需要单独校验、预览、提交和管理员审核，不能用 `sync` 代替。

`shopops-report --json status` 只读取本机缓存，不会主动刷新服务端或扫描项目。
验收应同时核对项目同步状态、`last_synced_at`、关联 SOP、当前设备及扫描状态：

- `synced`：最近一次项目同步成功，仍需检查数据新鲜度。
- `failed`：同步失败，结合错误码检查网络、权限或配置，旧数据不代表本次成功。
- `unsupported_server`：服务端不支持项目同步，先核对服务端兼容性。
- `pending_migration`：新设备等待管理员迁移确认，不代表已取得上报权限。

一个外部项目只保留一台当前设备。更换电脑时保留原项目身份，先停止旧电脑的
脚本和定时计划并完成待上传记录，再由管理员确认迁移。历史记录保留，旧电脑的
其他项目不受影响；撤销上报权限不代表 ShopOps 已远程停止旧电脑进程。

## 结果契约与定时采集

结果契约从 Reporter 0.3.0 起支持。在明确指定且已接入的项目中使用
`$shopops-result-contract`，由 Codex 在授权范围内分析真实输出，提出摘要、
指标、明细、完成声明和附件，再经开发者确认、校验、预览和提交后由管理员审核。
升级不会自动生成契约，退出码 0 也不能替代“完成了什么、获得了什么”的业务证据。

Windows 计划采集要求 Reporter 后台运行、PowerShell 可用且具备读取权限。
当前扫描范围为用户可见的 Windows 任务计划，不仅是已接入项目；项目映射需确认。
约 60 秒为采集周期，不是实时更新保证，休眠或后台停止时不会持续采集。

- 采集名称、启停、触发摘要、最近运行、下次运行及退出结果，不完整解析每周规则或重复间隔。
- 时间转为 UTC 上报，但计划时区字段固定为 `Asia/Shanghai`，非中国时区需与本机计划核对。
- 不采集 Linux cron、macOS 定时器或脚本内部定时器；macOS 支持 Reporter，不代表支持计划扫描。
- 不上传完整任务命令、参数、环境变量或 XML；任务名称和计划路径层级仍会采集，不应包含敏感信息。
- 扫描失败保留旧数据；未上报、不支持或失败不能解释为没有计划，也不能推断为手动运行。

## 授权与安全边界

- 支持 Reporter 环境探测、锁定版本安装、安全更新和只读诊断；
- 安装和诊断不扫描业务项目；明确请求项目接入或结果契约配置时，仅分析指定项目和获准读取的样例；
- 配对、项目配置写入、契约预览与提交、设备迁移和业务运行分别需要明确授权；
- 不因安装、升级或诊断而自动配对、生成项目配置、批准迁移或执行原脚本；
- 不索取或将私钥、配对码、Cookie、Token、密码写入 README、日志或共享诊断材料。

设备配对、项目初始化和业务运行由 Reporter CLI 完成。移除 Codex 插件不会删除
Reporter 身份、离线队列或项目配置。

插件安装和 `$` 技能调用方式参考
[OpenAI Plugins 文档](https://developers.openai.com/codex/plugins)；Marketplace
添加命令参考
[OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)。
