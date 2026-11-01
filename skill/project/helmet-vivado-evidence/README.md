# 24 Vivado资源、时序与截图取证

**形式：** 校验脚本＋操作清单。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

从匹配已实现工程提取DSP/BRAM/LUT/FF与时序，并指导报告截图。

## 所需输入

- 原178图的xpr或routed checkpoint
- 实现后utilization/timing报告
- bit/HWH身份与本次构建阶段

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-vivado-evidence`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 使用匹配工程Open Implemented Design，不为截图重新Run Implementation。
2. 资源看顶层，RAMB36+RAMB18/2换算BRAM Tile；不用子模块/不同位流结果相加。
3. 时序查看Design Timing Summary的Setup/Hold/Pulse Width、失败端点和约束覆盖，保留告警。
4. 清理版只做create_only时仅作结构图，不沿用旧178DSP资源或声称已上板。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/check_vivado_reports.py --utilization skill/_shared/fixtures/hardware_utilization.rpt --timing skill/_shared/fixtures/hardware_timing.rpt
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 资源/时序解析JSON
- 截图步骤和合适图名
- 硬件身份与验证阶段说明

## 失效条件与停止边界

- 只看正WNS不能证明所有路径被约束。
- 语法/结构生成通过不是布局布线通过。
- 替代43DSP图和178图不是同时驻留。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 原已布线报告顶层DSP178、LUT23463、FF24221、BRAM30.5；WNS0.949/WHS0.015/WPWS3.750ns，摘要失败端点0。

- [hardware](../../_shared/evidence/hardware.json)
- [vivado_reports](../../_shared/evidence/vivado_reports.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自DSP43/178/220解释、两种Vivado工程用途区分及资源/时序截图指导。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
