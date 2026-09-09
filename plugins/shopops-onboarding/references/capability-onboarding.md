# 完整接入：以服务端回执验收

本流程要求 Reporter 0.7.0 或更新版本，以及服务端对应 capabilities。基础上报可继续使用旧版本。安装来源必须与正式 manifest 和校验摘要一致。

## Codex 分析与角色绑定

读取实际任务入口、业务调用和输出，不执行模块来发现功能。根据主要工作选择 browser_executor、data_processor、ai_diagnoser、review_liaison；没有可靠依据则 role=null 并说明原因。一个项目共享一项角色，一次执行仍只有一条运行。用 office_role={role,reason,expected_revision} 声明并调用项目 sync，核对响应的有效绑定。人工覆盖优先，Codex 只能留下建议，不得自动恢复自动管理；角色本身不赋予执行或审批权限。不额外要求逐项目管理员批准角色。

## 补齐诊断、证据和环境

诊断格式 v2 包含 schema_version=2、external_run_key、带时区 generated_at、business_status（completed/partial/failed/unknown）、issues、impact、evidence_refs。成功也生成，issues 可以为空。诊断解释问题，不覆盖进程退出码和契约映射的业务结论。

从子进程环境读取 SHOPOPS_EXTERNAL_RUN_KEY 和 SHOPOPS_RUN_OUTPUT_DIR。每次优先写独立运行目录中与契约相同的相对路径；禁止用最近一次运行 ID 补写旧文件。证据只写声明的精确路径，禁止凭据、完整请求头、Cookie 和未脱敏客户数据。Reporter 在结束时冻结快照，补传不重新读取项目源文件。旧队列没有快照应报告 legacy_snapshot_unavailable，不能宣称完整证据。

Python 入口可调用 shopops_reporter.runtime_probe.write_application_environment() 记录实际解释器。Node/PowerShell 适配器在运行输出目录写 application-environment.json，带本次 external_run_key、runtime、version、architecture。无法确定保持 unknown；Reporter 的 Python 版本不能作为脚本环境。

改动 diagnostics/ai_readable_artifacts 或文件上传范围时，更新结果契约并经过现有审核。普通代码变更不自动重建 v2 契约。角色声明不进入结果契约摘要。

## 预览、受控验收与回执

使用 guided onboarding 的 configure-capabilities 操作预览配置变更，再 apply 已确认的精确 plan_id/digest；过期或源文件改变时重新预览。verify-capabilities 操作要求 spec 包含精确 command 和 safety_evidence；Codex 必须检查测试实现，证明不会写真实店铺。参数名含 dry-run 不足以证明安全。缺少受控入口就保持待验证，不运行真实 SOP。

受控运行记录 run_purpose=verification，使用同样设备身份、项目身份和已审核契约；不进入业务统计、SOP 最近运行或办公室实时动画。分别测试成功、失败及适用的部分完成。上报完成后通过 verification?version=2 保存服务端逐项验收，然后检查：

    shopops-report capabilities check --project-dir DIR --refresh --json

不加 --refresh 只读有时间戳的本地缓存，不能据此宣称新配置验收通过。回执必须匹配项目和配置摘要。八项为诊断格式、Reporter 版本、结构化错误、本次代码版本、实际脚本环境、AI 可读证据、办公室角色、定时计划；少项、待补传、未知来源均不能 complete。明确手动项目的调度可不适用；未知调度器不能当作手动。

交付分别列出安装健康、基础上报、八项完整性、实际有效角色、计划确认、未完成原因和回执时间。一次成功且无问题不取消已验证的结构化错误能力。不把代码已完成、候选构建完成、已发布和业务项目已适配混为一谈。


显式环境探测可以在 configure-capabilities 的 spec 中设置 application_environment={"mode":"explicit_probe","runtime":"Python","executable":"解释器绝对路径"}；runtime 也支持 Node、PowerShell。预览展示精确配置且不运行探测，实际运行结束后才执行固定版本查询；不可把业务入口作为解释器。进程内采集优先，失败保留 unknown。配置变化会使对应环境能力重新等待验收。
