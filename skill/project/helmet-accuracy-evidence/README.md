# 21 四类检测指标与成功示例追溯

**形式：** 校验脚本＋指标/图像证据模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

从固定测试记录提取每类P/R、TP/FP/FN及可用于报告的真实预测图。

## 所需输入

- 标注完整性和数据划分
- 预测数组/JSON与对应原图
- 阈值、IoU匹配定义和模型身份

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-accuracy-evidence`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 先区分浮点、混合精度、ARM/FPGA、现场与离线回放；REFERENCE人工框不算预测。
2. 按目标而非图像总数计算P/R；空场单独统计误报，不加入有目标召回分母。
3. 检索同帧ebike+rider+bare_head时保留全部预测/额外框，视觉复核框是否对准真实目标。
4. 图注注明版本和来源；置信度不是成功率，不用生成模型补造成功框。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/metrics_from_counts.py skill/_shared/fixtures/campus_counts.json
```

```bash
python skill/_shared/tools/find_examples.py --source 待检索结果目录 --require ebike rider bare_head
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 指标定义和每类计数
- 可追溯图片索引
- 报告图注与样本范围

## 失效条件与停止边界

- 部分只标头部的数据不能评估完整四类误检。
- 三类出现不等于三类全都正确，仍需视觉/IoU核对。
- 校园没有戴盔正样本就不能报校园戴盔召回。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 已核对校园开发集23张中14空场、9有目标；新混合模型三类TP/FP/FN分别9/2/0、7/2/1、2/2/5；成功案例不能代表整体达标。

- [accuracy](../../_shared/evidence/accuracy.json)
- [training](../../_shared/evidence/training.json)
- [arm_reference](../../_shared/evidence/arm_reference.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自用户要同时检出骑车/人/未戴盔的示例、曾误选室内图，以及浮点mAP和现场成功率混淆。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
