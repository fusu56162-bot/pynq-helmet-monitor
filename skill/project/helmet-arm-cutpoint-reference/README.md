# 07 ARM切分点与续算参考采集

**形式：** 提示词工作流＋数值校验模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

在前两层硬件化前确定ncnn边界与可恢复的原ARM输出。

## 所需输入

- 现有完整ARM运行时
- 原始同输入张量
- conv0/conv1切分与续算桥源码

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-arm-cutpoint-reference`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 先证明新桥full与原运行时full一致，再证明boundary→resume与full一致。
2. 保存整数累加、激活前后、再量化输入和原raw输出；固定shape/dtype/layout。
3. 把ARM参考采集标明未加载新FPGA，不将其作为硬件提速结果。
4. 仅在引用稳定后生成硬件常量并接上板验证。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 分层黄金张量索引
- full/boundary/resume等价报告
- 后续硬件接口定义

## 失效条件与停止边界

- 桥接full已偏离原算子时不能用它作黄金参考。
- 无清晰所有权的Mat引用可能在resume前失效。
- 采集未测时间时不得补写性能。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 修复后的真实ARM记录含原full、新bridge与切分续算等价检查；没有把该阶段当新FPGA实测。

- [arm_reference](../../_shared/evidence/arm_reference.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自首轮CopyTo加载失败、修复后ARM采集和双层参考路径分阶段推进。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
