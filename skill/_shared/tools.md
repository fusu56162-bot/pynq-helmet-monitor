# 共享工具说明

这些工具默认打印JSON，不运行模型/摄像头/FPGA，不改被检查的文件。`inspect_board.py --output`是例外：显式要求时新建报告，拒绝覆盖已有文件。`run_offline_checks.py`会在独立临时目录写故障fixture，结束后清理临时目录；可以用`--temp-root`选择已有可写目录。

| 工具 | 依赖 | 输入及边界 |
|---|---|---|
| inspect_board.py | Python3.8+标准库 | 当前主机元数据/容量；电脑上运行不是板卡证明 |
| verify_manifest.py | 标准库 | 平面SHA256映射或sha256子映射；拒绝逃出root的路径，不认证额外文件 |
| verify_release.py | 标准库 | 配套源码根目录和PROJECT_PROFILE；只核新模型param/bin/bit/HWH四文件 |
| audit_yolo_labels.py | 标准库 | images/labels、可选逐图确认空场名单；只查格式，不能判断像素中的真实目标 |
| compare_arrays.py | NumPy | 两个单独npy；默认位模式精确，显式容差仅用于浮点；失败返回1、输入错误2 |
| summarize_run.py | 标准库 | 当前摄像头RESULT或画质AUDIT已知schema；父子/并行计时不重复相加，帧龄和未知main指标不求和 |
| metrics_from_counts.py | 标准库 | 显式每类tp/fp/fn，空场另报；不代为匹配框或计算mAP |
| find_examples.py | NumPy | 结果目录/ZIP或预测JSONL，按同一条记录筛选类别共现，不补框，不将truth当预测，仍需视觉复核 |
| check_vivado_reports.py | 标准库 | 本项目层次资源报告和Design Timing Summary；只解析，不代替时序签核或真实上板 |

所有脚本都带`--help`。工具返回0表示当前声明范围成功，不等于整机/精度验收。例如图片索引没有候选可以正常返回0；读取到三个类别也不自动证明框都正确。

目录工具来源：环境采集/数组比较/计时摘要复用此前六项通用技能，项目副本的计时求和额外排除帧龄与未知指标；其余为本次提炼的离线检查工具。文件来源与本次验证见`../validation.json`及根目录`manifest.json`。

真实样例的CPU和FPGA raw来自历史同输入档案；未分发自然人照片、训练集、云端凭据、模型权重或位流。资源/时序RPT是原实现报告的原字节副本，可能含原设计遗留实例名称，不代表相关功能被当前应用启用。
