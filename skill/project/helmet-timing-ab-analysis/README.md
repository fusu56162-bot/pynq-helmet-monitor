# 20 411ms计时树与新旧模型同通路A/B

**形式：** 校验脚本＋性能复盘模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

解释整机2.4FPS、forward180/216ms、ARM续算154/187ms为何同时成立，并选下一步优化。

## 所需输入

- RESULT/AUDIT与计时代码
- 模型/位流/线程/频率与相机参数
- A/B顺序、预热和全部样本

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-timing-ab-analysis`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 建立父子计时和并行支路，ARM续算是forward子项，后台保存不再加主循环。
2. 抽查只发生在部分帧，用总耗时/总帧数摊销，不把每次抽查均值当每帧开销。
3. 离线模型比较用old→new→new→old同输入，不拿摄像头现场负载和裸forward混比。
4. 保留长尾而不任意删样本，用同口径占比估算Amdahl上限，再提出一项可测变化。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/summarize_run.py skill/_shared/fixtures/camera_result_excerpt.json
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 计时树与未归属时间
- 可比A/B结果
- 按收益上限排序的优化计划

## 失效条件与停止边界

- 1000/180ms不是整机摄像头FPS。
- 不同运行的最优数字拼接会产生错误总时间。
- 模型变更的微小延迟差异不等于新算法提速。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 归档新模型CPU204.27ms对FPGA+ARM180.31ms；单画面摄像头约2.43FPS。脚本可离线重算已归档窗口与抽查摊销。

- [ab_run](../../_shared/evidence/ab_run.json)
- [camera_run](../../_shared/evidence/camera_run.json)
- [quality](../../_shared/evidence/quality.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自31/150ms、411/216/187ms口径混淆，以及新旧模型实际同输入交错对照。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
