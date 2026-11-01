# 05 ONNX/ncnn导出与算子兼容

**形式：** 提示词工作流＋接口检查模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

固定224导出候选并处理当前ARM ncnn不支持的图算子。

## 所需输入

- 模型与导出代码版本
- MODEL_INTERFACE和转换日志
- ARM实际ncnn版本/编译选项及失败节点

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-export-ncnn-compat`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 分别保留PyTorch、TorchScript/ONNX和ncnn模型身份与固定形状。
2. 先逐节点定位不支持算子，如CopyTo，核对复制/别名/生命周期语义，不批量删节点。
3. 对兼容前后跑同一输入raw输出，再比较边界张量和检测框。
4. 生成独立兼容补丁包，标出它不等于量化、FPGA接入或精度验收。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 导出接口与算子差异表
- 最小兼容修复及回放对照
- 转换日志与文件哈希

## 失效条件与停止边界

- 能加载模型不代表输出语义未变。
- 转换器版本不同可能引入新算子。
- 改变输入形状不能仅修改ONNX入口标注。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 最终导出12组局部等价检查与真实ARM兼容后参考采集已有档案。

- [training](../../_shared/evidence/training.json)
- [arm_reference](../../_shared/evidence/arm_reference.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自首次新模型ARM加载报layer CopyTo not exists，兼容修复后才完成ARM参考采集。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
