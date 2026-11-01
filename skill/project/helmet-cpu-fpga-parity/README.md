# 10 同输入CPU/FPGA逐位一致性验收

**形式：** 校验脚本＋黄金数组样例。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

区分同输入实现正确与识别精度，验证当前178前段加ARM续算。

## 所需输入

- 同一输入的CPU raw、FPGA raw与边界
- 模型/硬件身份
- 明确逐位或容差规则

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-cpu-fpga-parity`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 先核shape/dtype，再查有限值和位模式，不只对最终框。
2. 定点、打包及当前精确参考按逐位；任何近似实现另立事先约定容差。
3. 完整forward与边界同时检验；未抽查帧不标CPU EXACT。
4. 用归档真实数组复现校验，明确这次离线重验未运行FPGA。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 逐位/容差检查JSON
- 首个差异位置与最大绝对差诊断
- 数值验收与精度验收分开的结论

## 失效条件与停止边界

- NaN即使两边相同也不通过有限值检查。
- 模型/输入不同的两个数组不能据此归因硬件。
- 0.73置信度或框相近不能代替raw一致性。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 包内提供一对来自真实CPU与FPGA档案的case_01 raw数组，可离线逐位复验；本次不重开板卡。

- [camera_run](../../_shared/evidence/camera_run.json)
- [ab_run](../../_shared/evidence/ab_run.json)
- [parity_pair](../../_shared/evidence/parity_pair.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自双层数值对照、摄像头启动12组核验和现场首帧/每10帧抽查。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
