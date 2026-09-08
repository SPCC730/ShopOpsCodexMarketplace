# ShopOps Onboarding

## 中文使用入口

统一接入向导已随 Reporter 0.5.0 发布。
兼容版本发布后，在新 Codex 任务中提供本机脚本或文件夹路径即可开始：

```text
请使用 $shopops-onboard 帮我接入 ShopOps，脚本位置是 <本机脚本或文件夹路径>。
先确认候选 SOP，默认完整接入一条；已有配置请续接。缺少输出时先展示修改建议，
真实运行前单独确认。最后核对本次运行、契约和附件的服务端验收证据。
```

同目录多个 SOP 使用独立任务配置；熟悉流程后可主动选择批量接入。
批量不运行脚本，待审核和待验收会保留进度。详见
[统一接入向导](references/guided-onboarding.md)。

当前离线发行版本为 Reporter **0.5.0**。本次增加结果契约 v2 与带签名的独立设备版本心跳，修复
设备列表版本滞后；需要兼容后端并在升级后重启 Reporter 后台，无需重新配对或运行业务脚本。
保留 0.4.1 的指纹和后台身份修复，安装包仍包含 `psutil`，旧项目的指纹迁移仍需独立确认。
详见[发行说明](../../README.md#reporter-042-更新说明)。

完整的管理员/开发者步骤向导运行在 ShopOps 独立说明书服务：

- 局域网：<http://192.168.10.201:5174>
- ShopOps 本机：<http://127.0.0.1:5174>

安装插件后请新建 Codex 任务，然后明确调用：

```text
请使用 $shopops-onboard 安装 ShopOps Reporter。展示完整安装预览，等我确认后再安装。
```

只读诊断使用：

```text
请使用 $shopops-doctor 只读诊断 ShopOps Reporter。
```

已有 Reporter 的电脑安全更新使用：

```text
请使用 $shopops-update 按 ShopOps 安全更新流程检查并升级 Reporter。先展示目标版本和影响范围，等我明确确认后再升级；不要重新配对、重新上传项目或运行业务脚本。
```

Reporter 配对、项目 `init`、脚本 `run`、结果查看和断网补传不属于 WP1 插件本身，
请按独立网页说明书继续操作。

项目需要展示看板时，可在项目 `.shopops/dashboard.json` 声明 `html` 静态文件或
`live_service` 私有局域网 HTTP 地址。接入时只读检查这份声明；不会把任意 `BaseUrl`
当作看板，也不会上传或代理看板内容。

`shopops-onboarding` provides the WP1 local installation and diagnosis path for
ShopOps Reporter. It supports Apple Silicon macOS and Windows x64 with CPython
3.11 and newer Python 3 versions, using platform-specific checksum-locked offline
wheelhouses. The current release contains locked wheels for CPython 3.11, 3.12,
3.13, and 3.14; newer versions require a published wheelhouse before they can be
installed. The
installer uses `pip --no-index` and never contacts PyPI.

Stable command paths:

- macOS: `~/.shopops-reporter/bin/shopops-report`
- Windows: `%LOCALAPPDATA%\ShopOps\Reporter\bin\shopops-report.cmd`

## Skills

- `shopops-onboard` probes the environment, previews the locked Reporter
  version and paths, waits for explicit developer confirmation, installs that
  exact version, and reports `shopops-report --json status`.
- `shopops-doctor` probes, validates the locked preview, inspects only the
  Reporter runtime and stable shim, and reports `healthy`, `not_installed`,
  `not_paired`, `upgrade_available`, or `repair_required`. It never repairs or
  changes runtime state.
- `shopops-update` compares the installed and checksum-locked Reporter versions,
  previews the machine-level update, waits for exact-version confirmation, and
  preserves device identity, project configuration, and the offline queue.
- `shopops-result-contract` analyzes an explicitly selected project, drafts a
  non-executable `.shopops/result-contract.yaml`, validates sanitized result
  samples, and submits the confirmed immutable contract for administrator review.

WP1 does not scan, connect to, or execute business projects, and it does not
enroll devices. It contains no MCP service, UI, browser extension, lifecycle
hook, cleanup command, publish, push, or merge workflow.

Removing this Codex plugin does not remove Reporter, its device identity, queue,
or project launch capability. Reporter cleanup is a separate explicit operation
outside WP1 and must preview affected runtime versions, identity, queued runs,
and projects before explicit confirmation. See
[the security policy](references/security-policy.md).
