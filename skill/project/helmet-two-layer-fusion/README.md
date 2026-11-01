# 13 178-DSP双层连续卷积与片上衔接

**形式：** 已验证案例模板＋硬件工作流。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

理解和复现当前两层3×3前段，在不改变模型语义的条件下评估进一步融合。

## 所需输入

- 匹配模型常量、chain_float.cpp和float_tail
- 两层参考边界及LUT
- HLS/Vivado报告与当前接口

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-two-layer-fusion`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 依次追踪重排量化、12→16步长1、激活再量化、16→32步长2、浮点尾部与HWC输出。
2. 核对层间FIFO/行缓存/固定权重，不把中间特征落DDR的旧方式当融合实现。
3. 新权重重新生成匹配ROM及硬件，保留INT8卷积＋浮点尾部的原语义。
4. 检查实现资源和100MHz时序，再做边界、完整forward及摄像头验收。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/check_vivado_reports.py --utilization skill/_shared/fixtures/hardware_utilization.rpt --timing skill/_shared/fixtures/hardware_timing.rpt
```

```bash
python skill/_shared/tools/verify_release.py --root .
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 可追溯两层数据流说明
- 常量与硬件匹配记录
- 实现/数值/速度证据链

## 失效条件与停止边界

- 178DSP只是前段，不是整网YOLO都进FPGA。
- 独立43DSP与178同时驻留直接相加为221，超过7020的220。
- 新结构create_only不能沿用旧图的资源/时序。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 匹配发布图实现178DSP、30.5BRAM、WNS0.949ns；后续真实摄像头与同输入记录核对其身份和输出。

- [hardware](../../_shared/evidence/hardware.json)
- [ab_run](../../_shared/evidence/ab_run.json)
- [camera_run](../../_shared/evidence/camera_run.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自用户要求硬件内部组织多步计算，连续层中间量化与权重驻留的生产方案。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
