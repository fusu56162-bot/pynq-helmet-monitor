# 12 3×3紧凑输入、行缓存与整层启动

**形式：** 案例模板＋负结果复盘。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

避免ARM重复复制邻域，设计3×3滑窗、输入/计算/输出流水与完整层测试。

## 所需输入

- kernel/stride/padding/dilation/groups
- 紧凑输入与输出布局
- ARM各阶段成本和候选HLS/RTL

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-spatial-streaming`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 按可达输入设计预填、三行缓存、左右padding、stride和尾部drain；dilation变化需重算行数。
2. 整层一次启动，保留各阶段token数、FIFO深度与回压检查。
3. 目标为减少展开/重复搬运，不把DDR带宽和端口竞争省略。
4. 先数值后整层时间；若候选更慢，保留负结果而不是称流式必然更快。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 滑窗与边界时序表
- 完整层端到端成本表
- 数值通过/速度通过两项结论

## 失效条件与停止边界

- DATAFLOW pragma不保证实际阶段重叠。
- 输出FIFO未消费或TLAST错误会死锁。
- 裸核时间不能对比完整ARM层。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** V3真实上板144数组、4716544值通过；18-DSP图整层仍比ARM慢约2.58–3.54倍，没有部署到摄像头。

- [v3](../../_shared/evidence/v3.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自整层流式V3紧凑输入与pack4目标，以及启动恢复后发现整层速度回退。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
