# ShopOps Codex Marketplace

公开的 ShopOps Codex 插件仓库。当前发布的 `shopops-onboarding 0.1.5`
用于安全安装和诊断 `ShopOps Reporter 0.1.4`。

完整交互式说明书：

- 局域网：<http://192.168.10.201:5174>
- ShopOps Mac mini 本机：<http://127.0.0.1:5174>

## 开发者 5 分钟开始

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

首次安装显示 `not_paired` 是正常状态；已经配对的电脑应显示 `healthy`。

锁定离线安装当前覆盖：

- Apple Silicon macOS，CPython 3.11/3.12；
- Windows 10/11 x64，CPython 3.11/3.12。

Windows 稳定命令位于
`%LOCALAPPDATA%\ShopOps\Reporter\bin\shopops-report.cmd`。Marketplace 根目录的
Python 版本只用于仓库开发测试，不是 Reporter 的运行版本约束。

### 4. 配对并接入项目

管理员在 ShopOps **外部接入** 页面生成一次性配对码。开发者使用
`shopops-report enroll` 配对电脑，然后在每个独立脚本项目副本中执行一次
`shopops-report init`。管理员确认待接入 SOP 后，日常运行只需：

```bash
shopops-report run
```

日志、结构化结果和明确声明的附件会进入 ShopOps **运行中心**。完整参数、正确
结果示例、断网补传和排障方式请查看交互式说明书。

## 当前能力边界

当前插件属于 WP1：

- 支持 Reporter 环境探测、锁定版本安装和只读诊断；
- 不扫描业务项目；
- 不自动配对设备；
- 不自动生成 `.shopops/`；
- 不执行原脚本。

设备配对、项目初始化和业务运行由 Reporter CLI 完成。移除 Codex 插件不会删除
Reporter 身份、离线队列或项目配置。

插件安装和 `$` 技能调用方式参考
[OpenAI Plugins 文档](https://developers.openai.com/codex/plugins)；Marketplace
添加命令参考
[OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)。
