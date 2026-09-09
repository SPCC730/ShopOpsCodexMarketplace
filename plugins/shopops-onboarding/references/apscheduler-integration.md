# APScheduler 接入

先静态核对依赖版本、scheduler 类型、executor、job ID 与启动入口。不导入业务模块发现计划，不读取 jobstore 的 pickle。当前适配器覆盖 APScheduler 3.10/3.11；4.x 明确返回 unsupported_apscheduler_version，不能显示为空计划。

在已有 scheduler 创建与 job 注册之后接入：

```python
from pathlib import Path
from shopops_reporter.scheduler_bridge import attach_scheduler
bridge = attach_scheduler(scheduler, instance_id="panel-main",
    export_path=Path(".shopops/apscheduler.json"),
    mappings={"daily-job": ["已确认的 integration_id"]})
# 应用退出时只关闭自己的桥接器：
# bridge.close()
```

桥接器只读取公开运行状态，保留原调度时间、函数、参数、重试、并发、misfire/coalesce 和 executor。不要为接入而替换 scheduler 或修改函数语义。原子 JSON 由运行中的桥接器生成，任意 jobs.json 不能作为已生效计划证据。三分钟未更新显示过期，读取文件时间不能覆盖 observed_at。

明确 job 与项目的映射后，用：

    shopops-report --json map-schedule --source apscheduler --instance-id panel-main --job-id daily-job --project-dir DIR --export-file FILE

此命令登记本地来源，下次同步生成待确认映射；管理员确认与开发者 accept-schedule 流程继续保留。接受 APS 映射时加 --source apscheduler，并使用服务端回执的 schedule_key、mapping_hash 及 integration:<integration_id> 稳定兼容标识。普通代码指纹变化不会新建计划。

调度事件与业务运行分开：triggered、misfired、max_instances_skipped、call_failed 不能自动变成业务成功。桥接器事件只取调度器提供的真实 scheduled_run_time(s)，不从 next_run_at 倒算。事件缓冲超过 500 项会报告截断，不能把它当成完整离线历史。

实际执行归属使用显式 ScheduleExecutionContext/ContextVar 或子进程专用参数。仅在包装入口能取得确切 occurrence 且已获映射确认时传递；不能用全局 os.environ 给并发任务设置归属。默认公开 listener 无法把 occurrence 无歧义地注入原 callable，因此默认标明“仅计划同步，触发关联未支持”；进程池、async 或自定义 executor 没有经过专门包装验收时也保持此状态。不可伪造业务 Run 来让办公室动起来。

同事项目无法访问时，只能报告公共适配器的合成验证结果；实际版本、executor 和项目接入仍待核实。
