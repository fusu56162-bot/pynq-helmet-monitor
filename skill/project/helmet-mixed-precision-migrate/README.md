# 06 FP32到混合精度发布迁移

**形式：** 案例模板＋校验工作流。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

保留224四类模型能力并生成当前55 INT8＋5 FP32路径，不把FP32评估直接当板端结果。

## 所需输入

- 新版浮点参考
- 训练集来源的校准清单
- 待恢复FP32层和完整/部分标注评估集

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-mixed-precision-migrate`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 校准样本仅来自训练划分，保留来源清单；当前示例128张不是通用强制值。
2. 量化后逐类比较raw误差和P/R，必要时恢复敏感层FP32并再评估。
3. 将固定权重/尺度/激活常量变化关联到新的硬件身份；不只替换bin就沿用旧ROM。
4. 在独立目录通过数值、精度和同通路速度检查后才提出切换。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/verify_release.py --root .
```

```bash
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 量化与恢复层记录
- 混合精度模型身份
- 精度差异及硬件再生成需求

## 失效条件与停止边界

- FP32精度不能替代INT8/混合精度精度。
- 未独立划分的校准/验证样本会泄漏。
- 当前FP32索引6/11/57/58/59只适用这版拓扑。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 当前发布混合模型与匹配178-DSP图已完成真实板端数值对照；校园未戴盔召回仍不足。

- [release_identity](../../_shared/evidence/release_identity.json)
- [arm_reference](../../_shared/evidence/arm_reference.json)
- [camera_run](../../_shared/evidence/camera_run.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自新模型替换、量化敏感头部漏检和固定FPGA常量需一起更新。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
