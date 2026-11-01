# 15 ARM续算、NEON与pack4边界成本

**形式：** 分析工作流＋优化取舍模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

在前段已由FPGA处理后，定位ncnn续算和布局/所有权转换的真实成本。

## 所需输入

- 同通路forward与owned_pack_and_suffix计时
- ncnn线程/NEON/编译选项
- 边界HWC与pack4代码及层级热点

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-arm-suffix-pack4`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 把续算看作forward子区间，不与forward重复相加；该段合并计时不能直接全归某个1×1算子。
2. 核查已有NEON和2线程，测布局、Mat所有权复制、缓存与剩余卷积/SiLU，不盲减线程。
3. 一次改一项并交错同输入A/B，比较数值、均值/中位数/尾部。
4. 若内存池或线程调整无收益，保存负结果，转向实测算子/数据流热点。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/summarize_run.py skill/_shared/fixtures/camera_result_excerpt.json
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 续算与桥接成本拆分
- 软件/硬件候选优先级
- 同输入验证与收益界限

## 失效条件与停止边界

- 线程更多或更少都不自动更快。
- 154ms离线续算与187ms摄像头续算运行负载不同。
- 不能把所有ARM耗时都叫YOLO或1×1耗时。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 新模型同输入forward约180.31ms，嵌套owned_pack_and_suffix约154.52ms；摄像头负载下可增至约187ms。

- [ab_run](../../_shared/evidence/ab_run.json)
- [quality](../../_shared/evidence/quality.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自ARM内存池/线程尝试无显著收益、预览竞争退化和新旧模型同输入对照。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
