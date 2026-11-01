# 14 完整层C++批量调度与接口对齐

**形式：** 提示词工作流＋交付接口模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

把逐tile Python调度迁到原生层调度，审查B修订候选而不改变现场主入口。

## 所需输入

- 原生pack4输入/输出所有权契约
- 批量命令与现有43-DSP接口
- ARM原算子、host故障测试和候选交付

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-native-layer-scheduling`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 先固定owned FP32 pack4→owned FP32 pack4 SiLU边界，避免与旧CHW导出时间混比。
2. 先静态身份与host整数参考、故障注入、缓冲拥有权，再真实ARM构建与浮点对照。
3. 只有这些通过后，按已获授权提供独立上板A/B及178恢复步骤。
4. 将第一版任务候选与修订任务候选分列，不整包覆盖公共类型/接口。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 原生ABI/所有权契约
- 分阶段验收矩阵
- ARM/板端待验收与回退说明

## 失效条件与停止边界

- host通过不能代替ARMv7浮点或真实FPGA性能。
- C++调用减少不保证核计算或DDR瓶颈消失。
- 43-DSP独立图未与178融合，不能累加宣称整网硬件覆盖。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 独立审查重算6组整数卷积、36数值与66故障/停止组；该审查阶段明确ARM和板端性能仍待验。

- [b_native](../../_shared/evidence/b_native.json)
- [b_arm](../../_shared/evidence/b_arm.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自B第一版210-DSP交付与任务错位、修订原生pack4层调度接收和独立预检。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
